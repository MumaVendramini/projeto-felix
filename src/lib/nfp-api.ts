export interface Cupom {
  id: number;
  organizacao_id: string;
  cnpj_organizacao: string;
  chave?: string | null;
  url_consulta?: string | null;
  data_emissao?: string | null;
  valor?: number | null;
  status: "processamento_urna" | "capturado_urna" | "processado_urna" | "erro";
  mensagem?: string | null;
  atualizado_em?: string;
  status_externo?: string | null;
  detalhe_externo?: string | null;
  data_processamento_externo?: string | null;
}

export interface ListCuponsResponse {
  itens: Cupom[];
  proximo: number | null;
}

export interface PatchExternoPayload {
  status_externo: string | null;
  detalhe_externo?: string | null;
  data_processamento_externo?: string | null;
  valor?: number | null;
  data_emissao?: string | null;
}

export const API_BASE_URL = "https://gestao-nfp.vercel.app/api/parceiro/v1";

export async function fetchCuponsApi(token: string, status = "processamento_urna", apos = 0, limite = 50): Promise<ListCuponsResponse> {
  const url = `${API_BASE_URL}/cupons?status=${status}&apos=${apos}&limite=${limite}`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Erro API Gestão NFP (${response.status}): ${errorText || response.statusText}`);
  }

  return response.json();
}

export async function patchCupomExternoApi(token: string, cupomId: number, payload: PatchExternoPayload) {
  const url = `${API_BASE_URL}/cupons/${cupomId}`;
  const response = await fetch(url, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Erro PATCH cupom #${cupomId} (${response.status}): ${errorText || response.statusText}`);
  }

  return response.json();
}

