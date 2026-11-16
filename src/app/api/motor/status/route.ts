import { NextRequest, NextResponse } from "next/server";
import { 
  obterEstadoMotor1, 
  adquirirTravaMotor1, 
  registrarPulsoNotaMotor1, 
  liberarTravaMotor1, 
  resetManualTravaMotor1 
} from "@/lib/motor-lock";

export async function GET() {
  const estado = obterEstadoMotor1();
  return NextResponse.json(estado);
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { acao, totalNotas, loteId, sucessoNota } = body;

    if (acao === "adquirir") {
      const res = adquirirTravaMotor1(totalNotas || 0, loteId);
      if (!res.sucesso) {
        return NextResponse.json({ error: res.motivo }, { status: 409 });
      }
      return NextResponse.json({ success: true, estado: obterEstadoMotor1() });
    }

    if (acao === "pulso") {
      const res = registrarPulsoNotaMotor1(sucessoNota ?? true);
      return NextResponse.json({ 
        success: true, 
        desarmarLote: res.desarmarLote, 
        motivo: res.motivo,
        estado: obterEstadoMotor1() 
      });
    }

    if (acao === "liberar") {
      liberarTravaMotor1("CONCLUIDO");
      return NextResponse.json({ success: true, estado: obterEstadoMotor1() });
    }

    if (acao === "reset_manual") {
      const novoEstado = resetManualTravaMotor1();
      return NextResponse.json({ success: true, estado: novoEstado });
    }

    return NextResponse.json({ error: `Ação '${acao}' inválida` }, { status: 400 });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || "Erro no gerenciador de trava" }, { status: 500 });
  }
}

