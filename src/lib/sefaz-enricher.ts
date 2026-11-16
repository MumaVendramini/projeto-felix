import https from "https";

export interface SefazEnrichResult {
  sucesso: boolean;
  valor: number | null;
  valorFormatado?: string | null;
  dataEmissao: string | null;
  cnpjEmitente: string | null;
  statusSefaz: string | null;
  temCpf: boolean;
  cpfConsumidor?: string | null;
  mensagem?: string;
  urlUsada: string;
}

function fetchHttpsHtml(url: string): Promise<{ statusCode: number; html: string }> {
  return new Promise((resolve, reject) => {
    const req = https.get(
      url,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          Accept:
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
          "Accept-Language": "pt-BR,pt;q=0.9",
          Connection: "keep-alive",
        },
      },
      (res) => {
        let data = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          data += chunk;
        });
        res.on("end", () => {
          resolve({ statusCode: res.statusCode || 200, html: data });
        });
      }
    );

    req.on("error", (err) => {
      reject(err);
    });

    req.setTimeout(12000, () => {
      req.destroy();
      reject(new Error("Timeout de 12s ao conectar na SEFAZ SP"));
    });
  });
}

/**
 * Consulta a SEFAZ SP pública (sem captcha) para enriquecer dados do cupom.
 * Aceita URL completa do QR Code ou chave de 44 dígitos.
 */
export async function consultarSefazSp(
  urlOuChave: string
): Promise<SefazEnrichResult> {
  let urlCompleta = "";

  if (urlOuChave.includes("?p=")) {
    urlCompleta = urlOuChave;
  } else {
    const chaveLimpa = urlOuChave.replace(/\D/g, "");
    if (chaveLimpa.length === 44) {
      urlCompleta = `https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=${chaveLimpa}|1|1|1|1`;
    } else {
      urlCompleta = urlOuChave;
    }
  }

  try {
    const { statusCode, html } = await fetchHttpsHtml(urlCompleta);

    // Se o portal retornou erro de QR Code inválido ou não suportado (ex: Modal de Erro)
    const matchErroQr = html.match(/Problemas na consulta via QR Code[^<]*/i);
    if (matchErroQr) {
      return {
        sucesso: false,
        valor: null,
        dataEmissao: null,
        cnpjEmitente: null,
        statusSefaz: "QR Code Inválido",
        temCpf: false,
        mensagem: matchErroQr[0].trim(),
        urlUsada: urlCompleta,
      };
    }

    // Se o WAF da Fazenda rejeitou a requisição (ex: HTTP 200 com 'Request Rejected')
    if (html.includes("The requested URL was rejected") || statusCode >= 400) {
      return {
        sucesso: false,
        valor: null,
        dataEmissao: null,
        cnpjEmitente: null,
        statusSefaz: "Rejeitado pela SEFAZ",
        temCpf: false,
        mensagem: "A SEFAZ bloqueou a requisição temporariamente (WAF).",
        urlUsada: urlCompleta,
      };
    }

    // 1. Extração de Valor (Ex: 60,64)
    let valorFormatado: string | null = null;
    let valorNumerico: number | null = null;

    const matchValor =
      html.match(/<span[^>]*class=["'][^"']*totalNumb\s+txtMax[^"']*["'][^>]*>([\d,\.]+)<\/span>/i) ||
      html.match(/Valor\s+a\s+pagar\s*R\$[\s\S]*?<span[^>]*class=["'][^"']*totalNumb[^"']*["'][^>]*>([\d,\.]+)<\/span>/i) ||
      html.match(/id=["']totalNota["'][^>]*>([\s\S]*?)<\//i);

    if (matchValor) {
      const vMatch = matchValor[1].match(/(\d+[,\.]\d{2})/);
      if (vMatch) valorFormatado = vMatch[1];
    }

    if (!valorFormatado) {
      const matchQualquerTotal = html.match(/<span[^>]*class=["'][^"']*totalNumb[^"']*["'][^>]*>([\d,\.]+)<\/span>/i);
      if (matchQualquerTotal) {
        const vMatch = matchQualquerTotal[1].match(/(\d+[,\.]\d{2})/);
        if (vMatch) valorFormatado = vMatch[1];
      }
    }

    if (valorFormatado) {
      valorNumerico = parseFloat(valorFormatado.replace(".", "").replace(",", "."));
    }

    // 2. Extração de Data de Emissão (Ex: 30/10/2026)
    let dataEmissao: string | null = null;
    const dataMatch = html.match(/Emissão:\s*<\/strong>\s*(\d{2}\/\d{2}\/\d{4})/i) ||
                      html.match(/(\d{2}\/\d{2}\/\d{4})/);
    if (dataMatch) {
      dataEmissao = dataMatch[1];
    }

    // 3. Extração do CNPJ do Emitente
    let cnpjEmitente: string | null = null;
    const cnpjMatch = html.match(/CNPJ:\s*([\d\.\/\-]+)/i) ||
                      html.match(/(\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2})/);
    if (cnpjMatch) {
      cnpjEmitente = cnpjMatch[1].trim();
    }

    // 4. Status na SEFAZ
    let statusSefaz = "Autorizada";
    if (html.includes("EMISSÃO NORMAL") || html.includes("Protocolo de Autorização")) {
      statusSefaz = "Autorizada";
    } else {
      const statusMatch = html.match(/(Cancelada|Denegada|Rejeitada|Inutilizada)/i);
      if (statusMatch) {
        statusSefaz = statusMatch[1];
      }
    }

    // 5. Checagem de CPF do Consumidor
    let temCpf = false;
    let cpfConsumidor: string | null = null;

    if (html.includes("Consumidor não identificado")) {
      temCpf = false;
    } else {
      const consumidorSection = html.match(/<h4>Consumidor<\/h4>[\s\S]*?<\/ul>/i);
      if (consumidorSection) {
        const cpfMatch = consumidorSection[0].match(/(\d{3}\.?\d{3}\.?\d{3}-?\d{2})/);
        if (cpfMatch) {
          temCpf = true;
          cpfConsumidor = cpfMatch[1];
        }
      }
    }

    return {
      sucesso: true,
      valor: valorNumerico,
      valorFormatado: valorFormatado ? `R$ ${valorFormatado}` : null,
      dataEmissao,
      cnpjEmitente,
      statusSefaz,
      temCpf,
      cpfConsumidor,
      mensagem: "Consulta realizada com sucesso na SEFAZ SP.",
      urlUsada: urlCompleta,
    };
  } catch (error: any) {
    return {
      sucesso: false,
      valor: null,
      dataEmissao: null,
      cnpjEmitente: null,
      statusSefaz: "Erro de Conexão",
      temCpf: false,
      mensagem: error.message || "Falha ao requisitar SEFAZ SP",
      urlUsada: urlCompleta,
    };
  }
}
