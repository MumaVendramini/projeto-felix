/**
 * Validador e Analisador de Chaves de Acesso da NFP (NF-e / NFC-e / SAT)
 *
 * Estrutura dos 44 dígitos:
 * [UF: 2d][AAMM: 4d][CNPJ: 14d][Mod: 2d][Série: 3d][Número: 9d][Tipo: 1d][Código: 8d][DV: 1d]
 */

export interface AnaliseChaveNfp {
  valida: boolean;
  chaveLimpa: string;
  uf: string;
  ano: number;
  mes: number;
  cnpjEmitente: string;
  modelo: string;
  dvInformado: number;
  dvCalculado: number;
  dvValido: boolean;
  dataLimiteEnvio: Date;
  dataLimiteFormatada: string;
  expirado: boolean;
  diasParaVencer: number;
  urgencia: "EXPIRADO" | "URGENTE" | "MODERADA" | "TRANQUILA";
  motivoInvalido?: string;
}

/**
 * Cálculo do Dígito Verificador Módulo 11 (padrão SEFAZ)
 * Pesos de 2 a 9 da direita para a esquerda.
 */
export function calcularDvModulo11(chave43: string): number {
  const pesos = [2, 3, 4, 5, 6, 7, 8, 9];
  let soma = 0;
  let pesoIndex = 0;

  for (let i = chave43.length - 1; i >= 0; i--) {
    const digito = parseInt(chave43[i], 10);
    soma += digito * pesos[pesoIndex];
    pesoIndex = (pesoIndex + 1) % pesos.length;
  }

  const resto = soma % 11;
  const dv = 11 - resto;
  if (dv === 0 || dv === 10 || dv === 11) {
    return 0;
  }
  return dv;
}

/**
 * Calcula a data limite de envio SEFAZ:
 * Regra: Dia 20 do segundo mês subsequente à emissão.
 * Ex: Emissão em 10/2026 -> Segundo mês subsequente é 12/2026 -> Limite: 20/12/2026.
 * Ex: Emissão em 11/2026 -> Segundo mês subsequente é 01/2027 -> Limite: 20/01/2027.
 */
export function calcularDataLimite(ano: number, mes: number): Date {
  let mesLimite = mes + 2;
  let anoLimite = ano;

  if (mesLimite > 12) {
    mesLimite -= 12;
    anoLimite += 1;
  }

  // Cria a data: anoLimite, mesLimite - 1 (0-indexed no JS), dia 20 às 23:59:59
  return new Date(anoLimite, mesLimite - 1, 20, 23, 59, 59);
}

/**
 * Analisa a chave de acesso, extrai metadados de emissão e calcula a janela legal de envio.
 */
export function analisarChaveNfp(
  chaveOuUrl: string,
  dataReferencia: Date = new Date()
): AnaliseChaveNfp {
  // Extrai apenas dígitos se for URL ou texto formatado
  let chaveLimpa = chaveOuUrl.replace(/\D/g, "");

  // Se tiver mais de 44 dígitos (por exemplo URL com parâmetros), procura um bloco de 44 dígitos
  if (chaveLimpa.length > 44) {
    const match = chaveOuUrl.match(/\b\d{44}\b/);
    if (match) {
      chaveLimpa = match[0];
    } else {
      chaveLimpa = chaveLimpa.slice(0, 44);
    }
  }

  if (chaveLimpa.length !== 44) {
    return {
      valida: false,
      chaveLimpa,
      uf: "",
      ano: 0,
      mes: 0,
      cnpjEmitente: "",
      modelo: "",
      dvInformado: 0,
      dvCalculado: 0,
      dvValido: false,
      dataLimiteEnvio: new Date(),
      dataLimiteFormatada: "N/D",
      expirado: true,
      diasParaVencer: -999,
      urgencia: "EXPIRADO",
      motivoInvalido: `Chave com ${chaveLimpa.length} dígitos (esperado 44).`,
    };
  }

  const uf = chaveLimpa.slice(0, 2);
  const aa = parseInt(chaveLimpa.slice(2, 4), 10);
  const mm = parseInt(chaveLimpa.slice(4, 6), 10);
  const cnpjEmitente = chaveLimpa.slice(6, 20);
  const modelo = chaveLimpa.slice(20, 22);
  const chave43 = chaveLimpa.slice(0, 43);
  const dvInformado = parseInt(chaveLimpa.slice(43, 44), 10);

  // Calcula ano completo (2000 + AA)
  const anoCompleto = 2000 + aa;

  // Validação matemática do DV
  const dvCalculado = calcularDvModulo11(chave43);
  const dvValido = dvCalculado === dvInformado;

  // Cálculo da data limite
  const dataLimiteEnvio = calcularDataLimite(anoCompleto, mm);

  const diffMs = dataLimiteEnvio.getTime() - dataReferencia.getTime();
  const diasParaVencer = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  const expirado = diasParaVencer < 0;

  let urgencia: AnaliseChaveNfp["urgencia"] = "TRANQUILA";
  if (expirado) {
    urgencia = "EXPIRADO";
  } else if (diasParaVencer <= 10) {
    urgencia = "URGENTE"; // Perto do dia 20 crítico!
  } else if (diasParaVencer <= 40) {
    urgencia = "MODERADA";
  }

  const diaStr = String(dataLimiteEnvio.getDate()).padStart(2, "0");
  const mesStr = String(dataLimiteEnvio.getMonth() + 1).padStart(2, "0");
  const anoStr = dataLimiteEnvio.getFullYear();
  const dataLimiteFormatada = `${diaStr}/${mesStr}/${anoStr}`;

  return {
    valida: dvValido && !expirado,
    chaveLimpa,
    uf,
    ano: anoCompleto,
    mes: mm,
    cnpjEmitente,
    modelo,
    dvInformado,
    dvCalculado,
    dvValido,
    dataLimiteEnvio,
    dataLimiteFormatada,
    expirado,
    diasParaVencer,
    urgencia,
    motivoInvalido: !dvValido
      ? `Dígito verificador inválido (calculado ${dvCalculado}, informado ${dvInformado})`
      : expirado
      ? `Prazo legal expirado em ${dataLimiteFormatada}`
      : undefined,
  };
}

