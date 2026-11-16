import { NextRequest, NextResponse } from "next/server";
import { fetchCuponsApi } from "@/lib/nfp-api";
import fs from "fs";
import path from "path";

// Caminho para o histórico persistido
const DATA_DIR = path.join(process.cwd(), "src", "data");
const HISTORICO_PATH = path.join(DATA_DIR, "historico_competencias.json");

interface CompetenciaStats {
  mesAno: string; // Ex: "11/2026"
  prazoLegal: string; // Ex: "20/01/2027"
  statusPrazo: "EM_DIA" | "ALERTA" | "EXPIRADO";
  totalNaBase: number;
  validadosAptosAguardando: number;
  comProblemaInelegivel: number;
  falhaSefazElegivel: number;
  separadosDigitacao: number;
  enviadosSefaz: number;
  rejeitadosPortal: number;
  totalEnriquecidoFaturavel: number;
  pendentesNaBase: number;
  grauAtingimentoPct: number;
  ultimaAtualizacao: string;
}

function calcularPrazoLegal(mesAno: string): { prazo: string; status: "EM_DIA" | "ALERTA" | "EXPIRADO" } {
  try {
    const [mesStr, anoStr] = mesAno.split("/");
    const mes = parseInt(mesStr, 10);
    const ano = parseInt(anoStr, 10);

    // Prazo legal: dia 20 do 2º mês subsequente
    // Ex: Emissão em Setembro (09) -> Outubro (1) -> Novembro (2) -> Prazo: 20/11
    let mesLimite = mes + 2;
    let anoLimite = ano;
    if (mesLimite > 12) {
      mesLimite -= 12;
      anoLimite += 1;
    }

    const dataLimite = new Date(anoLimite, mesLimite - 1, 20, 23, 59, 59);
    const hoje = new Date();
    const diffDias = Math.ceil((dataLimite.getTime() - hoje.getTime()) / (1000 * 60 * 60 * 24));

    const prazoFormatado = `20/${String(mesLimite).padStart(2, "0")}/${anoLimite}`;

    if (diffDias < 0) {
      return { prazo: prazoFormatado, status: "EXPIRADO" };
    } else if (diffDias <= 15) {
      return { prazo: prazoFormatado, status: "ALERTA" };
    } else {
      return { prazo: prazoFormatado, status: "EM_DIA" };
    }
  } catch {
    return { prazo: "--", status: "EM_DIA" };
  }
}

export async function GET(req: NextRequest) {
  try {
    const token = process.env.NFP_API_TOKEN;
    if (!token) {
      return NextResponse.json({ error: "Token não configurado" }, { status: 400 });
    }

    const { searchParams } = new URL(req.url);
    const mesFiltro = searchParams.get("mes") || "TODOS";

    // Busca ampla com paginação para levantar o volume real completo da base do parceiro
    let todosItens: any[] = [];
    let cursorApos = 0;
    let maxPages = 15; // Até 7.500 cupons em lote rápido
    let page = 0;

    while (page < maxPages) {
      page++;
      const data = await fetchCuponsApi(token, "todos", cursorApos, 500);
      if (!data.itens || data.itens.length === 0) break;
      todosItens = todosItens.concat(data.itens);

      if (!data.proximo || data.proximo === cursorApos) break;
      cursorApos = data.proximo;
    }

    // Regra Contratual Estrita: O escopo do projeto é de SETEMBRO/2026 em diante (AAMM >= 2609)
    // Qualquer cupom de Agosto/2026 ou anterior é sumariamente excluído de todo o painel e métricas.
    todosItens = todosItens.filter((c) => {
      if (!c.chave || c.chave.length !== 44) return false;
      const aamm = parseInt(c.chave.slice(2, 6), 10);
      return !isNaN(aamm) && aamm >= 2609;
    });

    // Identificar e agrupar todas as competências (MM/AAAA)
    const mapaPorMes: Record<string, any[]> = {};
    todosItens.forEach((c) => {
      let mesAno = "DESCONHECIDO";
      if (c.chave && c.chave.length === 44) {
        const aa = c.chave.slice(2, 4);
        const mm = c.chave.slice(4, 6);
        mesAno = `${mm}/20${aa}`;
      }
      if (!mapaPorMes[mesAno]) {
        mapaPorMes[mesAno] = [];
      }
      mapaPorMes[mesAno].push(c);
    });

    const competenciasDisponiveis = Object.keys(mapaPorMes)
      .filter((k) => k !== "DESCONHECIDO")
      .sort()
      .reverse();

    // Carrega histórico persistido se existir
    let historicoArmazenado: Record<string, CompetenciaStats> = {};
    try {
      if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
      }
      if (fs.existsSync(HISTORICO_PATH)) {
        const raw = fs.readFileSync(HISTORICO_PATH, "utf-8");
        historicoArmazenado = JSON.parse(raw);
      }
    } catch (e) {
      console.warn("Falha ao ler histórico local:", e);
    }

    // Calcula as métricas consolidadas por competência
    const tabelaCompetencias: CompetenciaStats[] = competenciasDisponiveis.map((mesAno) => {
      const itensDoMes = mapaPorMes[mesAno] || [];
      const totalNaBase = itensDoMes.length;

      // Estritamente os que estão aguardando digitação (ENRIQUECIDO_APTO)
      const validadosAptosAguardando = itensDoMes.filter(
        (c) => c.status_externo === "ENRIQUECIDO_APTO"
      ).length;

      // Inelegíveis por CPF no caixa ou legalmente expirados
      const comProblemaInelegivel = itensDoMes.filter(
        (c) => c.status_externo === "INELEGIVEL_CPF" || c.status_externo === "EXPIRADO"
      ).length;

      // Falha temporária da consulta SEFAZ mas chave/DV OK
      const falhaSefazElegivel = itensDoMes.filter(
        (c) => c.status_externo === "ENRIQUECIMENTO_FALHOU_CHAVE_OK"
      ).length;

      // Cupons em lote pelo Motor 2 (Claude)
      const separadosDigitacao = itensDoMes.filter(
        (c) => c.status_externo === "SEPARADO_DIGITACAO"
      ).length;

      // Cupons enviados com sucesso para a SEFAZ
      const enviadosSefaz = itensDoMes.filter(
        (c) => c.status_externo === "ENVIADO_SEFAZ" || c.status_externo === "CONFIRMADO_RELATORIO"
      ).length;

      // Rejeições reportadas pelo portal da SEFAZ
      const rejeitadosPortal = itensDoMes.filter(
        (c) => c.status_externo === "REJEITADO_PORTAL"
      ).length;

      // Total processado/trabalhado na esteira
      const totalProcessado =
        validadosAptosAguardando +
        comProblemaInelegivel +
        falhaSefazElegivel +
        separadosDigitacao +
        enviadosSefaz +
        rejeitadosPortal;

      const pendentesNaBase = Math.max(0, totalNaBase - totalProcessado);
      const grauAtingimentoPct = totalNaBase > 0 ? Math.round((totalProcessado / totalNaBase) * 100) : 0;
      const { prazo, status } = calcularPrazoLegal(mesAno);

      const stats: CompetenciaStats = {
        mesAno,
        prazoLegal: prazo,
        statusPrazo: status,
        totalNaBase,
        validadosAptosAguardando,
        comProblemaInelegivel,
        falhaSefazElegivel,
        separadosDigitacao,
        enviadosSefaz,
        rejeitadosPortal,
        totalEnriquecidoFaturavel: totalProcessado,
        pendentesNaBase,
        grauAtingimentoPct,
        ultimaAtualizacao: new Date().toISOString(),
      };

      // Atualiza o histórico persistido
      historicoArmazenado[mesAno] = stats;
      return stats;
    });

    // Salva o histórico atualizado
    try {
      fs.writeFileSync(HISTORICO_PATH, JSON.stringify(historicoArmazenado, null, 2), "utf-8");
    } catch (e) {
      console.warn("Falha ao salvar histórico local:", e);
    }

    // Filtra para os 4 Cards principais de acordo com o filtro selecionado
    const itensFiltrados =
      mesFiltro === "TODOS"
        ? todosItens
        : todosItens.filter((c) => {
            if (!c.chave || c.chave.length !== 44) return false;
            const aa = c.chave.slice(2, 4);
            const mm = c.chave.slice(4, 6);
            return `${mm}/20${aa}` === mesFiltro;
          });

    const totalNaBase = itensFiltrados.length;

    // Motor 1: Validados e Enriquecidos (preserva o histórico de quem já avançou para o Motor 2)
    const validadosAptos = itensFiltrados.filter(
      (c) =>
        c.status_externo === "ENRIQUECIDO_APTO" ||
        c.status_externo === "SEPARADO_DIGITACAO" ||
        c.status_externo === "ENVIADO_SEFAZ" ||
        c.status_externo === "CONFIRMADO_RELATORIO"
    ).length;

    const comProblemaInelegivel = itensFiltrados.filter(
      (c) => c.status_externo === "INELEGIVEL_CPF" || c.status_externo === "EXPIRADO"
    ).length;

    const falhaSefazMasElegivel = itensFiltrados.filter(
      (c) => c.status_externo === "ENRIQUECIMENTO_FALHOU_CHAVE_OK"
    ).length;

    const totalEnriquecidoFaturavel = validadosAptos + comProblemaInelegivel + falhaSefazMasElegivel;
    const pendentesNaBase = Math.max(0, totalNaBase - totalEnriquecidoFaturavel);
    const grauAtingimentoPct = totalNaBase > 0 ? Math.round((totalEnriquecidoFaturavel / totalNaBase) * 100) : 0;

    // Motor 2 (Digitação)
    const enviadosSefaz = itensFiltrados.filter((c) => c.status_externo === "ENVIADO_SEFAZ").length;
    const confirmadosRelatorio = itensFiltrados.filter((c) => c.status_externo === "CONFIRMADO_RELATORIO").length;
    const rejeitadosPortal = itensFiltrados.filter((c) => c.status_externo === "REJEITADO_PORTAL").length;
    const separadosDigitacao = itensFiltrados.filter((c) => c.status_externo === "SEPARADO_DIGITACAO").length;
    const totalConcluidosDigitacao = enviadosSefaz + confirmadosRelatorio;

    return NextResponse.json({
      success: true,
      motor1Enriquecimento: {
        totalEnriquecidoFaturavel,
        totalNaBase,
        pendentesNaBase,
        validadosAptos,
        comProblemaInelegivel,
        falhaSefazMasElegivel,
      },
      competenciasDisponiveis,
      mesSelecionado: mesFiltro,
      tabelaCompetencias,
      resumoMes: {
        totalMes: totalNaBase,
        enriquecidosMes: totalEnriquecidoFaturavel,
        faltamMes: pendentesNaBase,
        grauAtingimentoPct,
      },
      motor2Digitacao: {
        totalConcluidosCobravel: totalConcluidosDigitacao,
        enviadosSefaz,
        confirmadosRelatorio,
        rejeitadosPortal,
        separadosDigitacao,
      },
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
