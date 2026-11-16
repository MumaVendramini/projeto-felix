import { NextRequest, NextResponse } from "next/server";
import { consultarSefazSp } from "@/lib/sefaz-enricher";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { urlOuChave } = body;

    if (!urlOuChave) {
      return NextResponse.json(
        { error: "URL do QR Code ou Chave de 44 dígitos é obrigatória." },
        { status: 400 }
      );
    }

    const resultado = await consultarSefazSp(urlOuChave);
    return NextResponse.json(resultado);
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Erro interno ao enriquecer na SEFAZ." },
      { status: 500 }
    );
  }
}

