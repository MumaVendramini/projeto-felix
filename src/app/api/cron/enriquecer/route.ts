import { NextRequest, NextResponse } from "next/server";
import { fetchCuponsApi, patchCupomExternoApi } from "@/lib/nfp-api";
import { consultarSefazSp } from "@/lib/sefaz-enricher";
import { analisarChaveNfp } from "@/lib/nfp-chave-validator";
import { 
  adquirirTravaMotor1, 
  registrarPulsoNotaMotor1, 
  liberarTravaMotor1 
} from "@/lib/motor-lock";

// Configura tempo limite máximo permitido na Vercel (60 segundos)
export const maxDuration = 60;

// Processa 20 notas em lote seguro com ritmo humano aleatório
const LOTE_CRON = 20;

// Jitter aleatório humano (1.5s a 2.8s) para comportamento indetectável no WAF/F5 da SEFAZ
const obterDelayAleatorioMs = () => Math.floor(Math.random() * (2800 - 1500 + 1)) + 1500;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function GET(req: NextRequest) {
  const token = process.env.NFP_API_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "Token NFP_API_TOKEN não configurado no ambiente." }, { status: 500 });
  }

  // 1. Tenta adquirir a trava do motor para evitar dupla execução
  const lock = adquirirTravaMotor1(LOTE_CRON, `cron-${Date.now()}`);
  if (!lock.sucesso) {
    return NextResponse.json({
      success: false,
      mensagem: "Outro processo do Motor 1 já está em execução no momento.",
      motivo: lock.motivo,
    });
  }

  const resultados = {
    processados: 0,
    aptos: 0,
    inelegiveisCpf: 0,
    expirados: 0,
    falhasChaveOk: 0,
    erros: 0,
  };

  try {
    // 2. Busca cupons pendentes com priorização por Prazo Legal (Deadline First)
    let cuponsPendentes: any[] = [];
    let cursorApos = 0;
    let tentativas = 0;

    while (cuponsPendentes.length < LOTE_CRON * 3 && tentativas < 15) {
      tentativas++;
      const data = await fetchCuponsApi(token, "todos", cursorApos, 100);
      if (!data.itens || data.itens.length === 0) break;

      for (const c of data.itens) {
        // Ignora Agosto e anteriores
        if (!c.chave || c.chave.length !== 44) continue;
        const aamm = parseInt(c.chave.slice(2, 6), 10);
        if (isNaN(aamm) || aamm < 2609) continue;

        const st = c.status_externo;
        const jaFinalizado =
          st === "ENRIQUECIDO_APTO" ||
          st === "INELEGIVEL_CPF" ||
          st === "EXPIRADO" ||
          st === "ENRIQUECIMENTO_FALHOU_CHAVE_OK" ||
          st === "SEPARADO_DIGITACAO" ||
          st === "ENVIADO_SEFAZ" ||
          st === "CONFIRMADO_RELATORIO";

        if (!jaFinalizado) {
          cuponsPendentes.push(c);
        }
      }

      if (!data.proximo || data.proximo === cursorApos) break;
      cursorApos = data.proximo;
    }

    if (cuponsPendentes.length === 0) {
      liberarTravaMotor1("CONCLUIDO");
      return NextResponse.json({
        success: true,
        mensagem: "Fila limpa! Nenhum cupom pendente de enriquecimento no momento.",
        resultados,
      });
    }

    // Ordenação por Prazo Legal: menor AAMM primeiro (Setembro antes de Outubro)
    cuponsPendentes.sort((a, b) => {
      const aammA = parseInt(a.chave.slice(2, 6), 10);
      const aammB = parseInt(b.chave.slice(2, 6), 10);
      return aammA - aammB;
    });

    const loteParaProcessar = cuponsPendentes.slice(0, LOTE_CRON);

    // 3. Processamento sequencial do lote
    for (const cupom of loteParaProcessar) {
      resultados.processados++;

      const payload = cupom.url_consulta || cupom.chave;
      const analise = analisarChaveNfp(payload);

      // Descarte de expirados
      if (analise.expirado) {
        await patchCupomExternoApi(token, cupom.id, {
          status_externo: "EXPIRADO",
          detalhe_externo: `Prazo legal expirou em ${analise.dataLimiteFormatada}`,
          data_processamento_externo: new Date().toISOString(),
        });
        resultados.expirados++;
        registrarPulsoNotaMotor1(true);
        continue;
      }

      // Consulta SEFAZ pública com bypass
      try {
        const enriquecido = await consultarSefazSp(payload);

        if (enriquecido.sucesso) {
          const statusGravacao = enriquecido.temCpf ? "INELEGIVEL_CPF" : "ENRIQUECIDO_APTO";
          const detalheGravacao = enriquecido.temCpf ? "Consumidor cadastrou CPF no caixa" : null;

          let dataEmissaoFormatada: string | null = null;
          if (enriquecido.dataEmissao) {
            const p = enriquecido.dataEmissao.split("/");
            if (p.length === 3) dataEmissaoFormatada = `${p[2]}-${p[1]}-${p[0]}`;
          }

          await patchCupomExternoApi(token, cupom.id, {
            status_externo: statusGravacao,
            detalhe_externo: detalheGravacao,
            data_processamento_externo: new Date().toISOString(),
            valor: enriquecido.valor,
            data_emissao: dataEmissaoFormatada,
          });

          if (enriquecido.temCpf) {
            resultados.inelegiveisCpf++;
          } else {
            resultados.aptos++;
          }
          registrarPulsoNotaMotor1(true);
        } else {
          // Falha na SEFAZ pública: se a chave matemática for válida, salva CHAVE_OK
          if (analise.dvValido) {
            await patchCupomExternoApi(token, cupom.id, {
              status_externo: "ENRIQUECIMENTO_FALHOU_CHAVE_OK",
              detalhe_externo: enriquecido.mensagem || "Consulta SEFAZ indisponivel, chave e DV validos",
              data_processamento_externo: new Date().toISOString(),
            });
            resultados.falhasChaveOk++;
          } else {
            resultados.erros++;
          }
          registrarPulsoNotaMotor1(false);
        }
      } catch (err: any) {
        resultados.erros++;
        registrarPulsoNotaMotor1(false);
      }

      // Delay de proteção anti-bloqueio com ritmo humano aleatório
      await sleep(obterDelayAleatorioMs());
    }

    liberarTravaMotor1("CONCLUIDO");

    return NextResponse.json({
      success: true,
      mensagem: `Ciclo do Cron concluído com sucesso: ${resultados.processados} cupons processados.`,
      resultados,
    });
  } catch (error: any) {
    liberarTravaMotor1("ERRO_FATAL");
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
