import { NextRequest, NextResponse } from "next/server";
import { fetchCuponsApi, patchCupomExternoApi } from "@/lib/nfp-api";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    let { action, token, limite = 1, apos = 0, cupomId, payloadExterno } = body;

    // Se o usuário não enviou o token na requisição, usa o token configurado no ambiente (.env.local)
    if (!token || !token.trim()) {
      token = process.env.NFP_API_TOKEN;
    }

    if (!token) {
      return NextResponse.json(
        { error: "Token de autorização (Bearer nfpp_...) não informado e nem configurado no .env.local." },
        { status: 400 }
      );
    }

    if (action === "test_connection") {
      const data = await fetchCuponsApi(token, "processamento_urna", 0, 1);
      return NextResponse.json({
        success: true,
        message: "Conexão com a API Gestão NFP estabelecida com sucesso!",
        totalRetornado: data.itens.length,
        proximo: data.proximo,
      });
    }

    if (action === "fetch_cupons") {
      // Varredura Total da Base: percorre todas as páginas de cupons para montar a fila real completa
      // e entregar prioritariamente a competência mais urgente (Setembro/2026 vence no dia 20/11)
      const cuponsPendentes: any[] = [];
      let cursorApos = 0; // Sempre varre a fila inteira para encontrar a prioridade máxima global
      let tentativas = 0;
      let ultimoProximo: number | null = null;
      const maxVarredura = 15; // Até 1.500 cupons (cobre os 535 existentes em segundos)

      while (tentativas < maxVarredura) {
        tentativas++;
        const data = await fetchCuponsApi(token, "processamento_urna", cursorApos, 100);
        ultimoProximo = data.proximo;

        if (!data.itens || data.itens.length === 0) {
          break;
        }

        // Coleta apenas quem ainda está pendente de processamento
        for (const c of data.itens) {
          const status = c.status_externo;
          const jaFinalizado = 
            status === "ENRIQUECIDO_APTO" ||
            status === "INELEGIVEL_CPF" ||
            status === "EXPIRADO" ||
            status === "ENRIQUECIMENTO_FALHOU_CHAVE_OK" ||
            status === "SEPARADO_DIGITACAO" ||
            status === "ENVIADO_SEFAZ" ||
            status === "CONFIRMADO_RELATORIO";

          if (!jaFinalizado) {
            cuponsPendentes.push(c);
          }
        }

        if (!data.proximo || data.proximo === cursorApos) {
          break;
        }
        cursorApos = data.proximo;
      }

      // 1. Filtro de Expiração Legal: Descarta quem já venceu (Ex: Agosto/2026 expirou em 20/10/2026)
      const hoje = new Date();
      const cuponsVivos: any[] = [];

      for (const c of cuponsPendentes) {
        if (c.chave && c.chave.length === 44) {
          const aa = parseInt(c.chave.slice(2, 4), 10);
          const mm = parseInt(c.chave.slice(4, 6), 10);
          let mesLimite = mm + 2;
          let anoLimite = 2000 + aa;
          if (mesLimite > 12) {
            mesLimite -= 12;
            anoLimite += 1;
          }
          const dataLimite = new Date(anoLimite, mesLimite - 1, 20, 23, 59, 59);

          // Se já passou da data limite, está expirado para doação -> descarta da esteira de enriquecimento
          if (dataLimite.getTime() < hoje.getTime()) {
            continue;
          }
        }
        cuponsVivos.push(c);
      }

      // 2. Ordenação por Urgência Legal (Deadline First) garantida em toda a base:
      // Ex: Setembro (2609) SEMPRE virá antes de Outubro (2610) e Novembro (2611)
      cuponsVivos.sort((a, b) => {
        const aammA = a.chave && a.chave.length === 44 ? parseInt(a.chave.slice(2, 6), 10) : 9999;
        const aammB = b.chave && b.chave.length === 44 ? parseInt(b.chave.slice(2, 6), 10) : 9999;
        return aammA - aammB;
      });

      // Retorna exatamente a quantidade solicitada pelo lote priorizando os vivos mais urgentes (Setembro)
      const lotePriorizado = cuponsVivos.slice(0, limite);

      return NextResponse.json({
        success: true,
        message: `Busca concluída: ${lotePriorizado.length} cupons recuperados com priorização por prazo legal (vencimento mais próximo primeiro).`,
        itens: lotePriorizado,
        proximo: ultimoProximo,
      });
    }

    if (action === "patch_externo") {
      if (!cupomId || !payloadExterno) {
        return NextResponse.json(
          { error: "cupomId e payloadExterno são obrigatórios para patch_externo." },
          { status: 400 }
        );
      }
      const data = await patchCupomExternoApi(token, cupomId, payloadExterno);
      return NextResponse.json({
        success: true,
        message: `Cupom #${cupomId} atualizado no banco do parceiro com sucesso.`,
        resultado: data,
      });
    }

    return NextResponse.json(
      { error: `Ação '${action}' não reconhecida.` },
      { status: 400 }
    );
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Erro interno ao processar gatilho." },
      { status: 500 }
    );
  }
}
