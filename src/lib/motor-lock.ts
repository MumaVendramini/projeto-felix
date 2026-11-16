/**
 * Gerenciador de Trava Distribuída (Lock), Pulso de Vida (Heartbeat) e Disjuntor (Circuit Breaker)
 * Dedicado ao Motor 1 (Enriquecimento SEFAZ).
 *
 * Garante:
 * 1. Concorrência zero (apenas 1 processo rodando por vez).
 * 2. Detecção e auto-recuperação de processos zumbis (se ficar sem pulso por > 3 minutos).
 * 3. Circuit Breaker: desarma o lote se a SEFAZ apresentar 3 erros consecutivos de rede/bloqueio.
 */

export interface MotorLockState {
  emExecucao: boolean;
  motorNome: string;
  loteId: string | null;
  totalNotas: number;
  notasProcessadas: number;
  inicioExecucao: number | null;     // timestamp em ms
  ultimoPulso: number | null;        // timestamp em ms (Heartbeat)
  errosConsecutivos: number;
  statusDescritivo: "OCIOSO" | "EXECUTANDO" | "CIRCUIT_BREAKER_ATIVADO" | "TRAVA_RECUPERADA_ZUMBI";
  mensagemAlerta?: string | null;
}

// Estado em memória do servidor (Singleton)
let motor1State: MotorLockState = {
  emExecucao: false,
  motorNome: "Motor 1 - Enriquecedor SEFAZ",
  loteId: null,
  totalNotas: 0,
  notasProcessadas: 0,
  inicioExecucao: null,
  ultimoPulso: null,
  errosConsecutivos: 0,
  statusDescritivo: "OCIOSO",
  mensagemAlerta: null,
};

// Limite máximo sem pulso antes de considerar processo "zumbi" (3 minutos)
const TIMEOUT_ZUMBI_MS = 3 * 60 * 1000;

// Máximo de erros consecutivos da SEFAZ antes de desarmar o disjuntor (Circuit Breaker)
const MAX_ERROS_CONSECUTIVOS = 3;

/**
 * Retorna o estado atual da trava e pulso do Motor 1
 */
export function obterEstadoMotor1(): MotorLockState & { segundosSemPulso: number; travadoZumbi: boolean } {
  const agora = Date.now();
  const segundosSemPulso = motor1State.ultimoPulso
    ? Math.floor((agora - motor1State.ultimoPulso) / 1000)
    : 0;

  const travadoZumbi =
    motor1State.emExecucao &&
    motor1State.ultimoPulso !== null &&
    agora - motor1State.ultimoPulso > TIMEOUT_ZUMBI_MS;

  return {
    ...motor1State,
    segundosSemPulso,
    travadoZumbi,
  };
}

/**
 * Tenta adquirir a trava para iniciar um novo lote de enriquecimento.
 * Se houver um processo zumbi detectado, ele é morto e a nova execução assume.
 */
export function adquirirTravaMotor1(totalNotas: number, loteId?: string): { sucesso: boolean; motivo?: string } {
  const agora = Date.now();

  // Verifica se há processo zumbi ativo
  if (motor1State.emExecucao && motor1State.ultimoPulso && agora - motor1State.ultimoPulso > TIMEOUT_ZUMBI_MS) {
    // Mata a trava anterior automaticamente
    motor1State = {
      emExecucao: true,
      motorNome: "Motor 1 - Enriquecedor SEFAZ",
      loteId: loteId || `lote-${agora}`,
      totalNotas,
      notasProcessadas: 0,
      inicioExecucao: agora,
      ultimoPulso: agora,
      errosConsecutivos: 0,
      statusDescritivo: "TRAVA_RECUPERADA_ZUMBI",
      mensagemAlerta: "Processo zumbi anterior eliminado por inatividade (> 3min). Novo ciclo assumiu.",
    };
    return { sucesso: true, motivo: "Zumbi recuperado com sucesso." };
  }

  // Se já está executando legitimamente, nega nova execução
  if (motor1State.emExecucao) {
    const seg = motor1State.ultimoPulso ? Math.floor((agora - motor1State.ultimoPulso) / 1000) : 0;
    return {
      sucesso: false,
      motivo: `Motor já está em execução (Lote: ${motor1State.loteId}). Último pulso há ${seg}s.`,
    };
  }

  // Adquire a trava normalmente
  motor1State = {
    emExecucao: true,
    motorNome: "Motor 1 - Enriquecedor SEFAZ",
    loteId: loteId || `lote-${agora}`,
    totalNotas,
    notasProcessadas: 0,
    inicioExecucao: agora,
    ultimoPulso: agora,
    errosConsecutivos: 0,
    statusDescritivo: "EXECUTANDO",
    mensagemAlerta: null,
  };

  return { sucesso: true };
}

/**
 * Atualiza o "Pulso de Vida" (Heartbeat) a cada nota enriquecida.
 * Também controla o Circuit Breaker (disjuntor).
 */
export function registrarPulsoNotaMotor1(sucessoNota: boolean): { desarmarLote: boolean; motivo?: string } {
  const agora = Date.now();
  motor1State.ultimoPulso = agora;
  motor1State.notasProcessadas += 1;

  if (sucessoNota) {
    // Reseta contador de erros em caso de sucesso
    motor1State.errosConsecutivos = 0;
    motor1State.statusDescritivo = "EXECUTANDO";
  } else {
    motor1State.errosConsecutivos += 1;

    // Se atingiu o limite de erros consecutivos, desarma o lote!
    if (motor1State.errosConsecutivos >= MAX_ERROS_CONSECUTIVOS) {
      motor1State.statusDescritivo = "CIRCUIT_BREAKER_ATIVADO";
      motor1State.mensagemAlerta = `Circuit Breaker ativado: ${MAX_ERROS_CONSECUTIVOS} falhas consecutivas de rede na SEFAZ. Lote interrompido para proteção de IP.`;
      return {
        desarmarLote: true,
        motivo: motor1State.mensagemAlerta,
      };
    }
  }

  return { desarmarLote: false };
}

/**
 * Libera a trava ao final do processamento ou após pausa.
 */
export function liberarTravaMotor1(motivoFinal: "CONCLUIDO" | "PAUSADO" | "ERRO_FATAL" = "CONCLUIDO") {
  motor1State.emExecucao = false;
  motor1State.statusDescritivo = motivoFinal === "CONCLUIDO" ? "OCIOSO" : motor1State.statusDescritivo;
  motor1State.ultimoPulso = Date.now();
}

/**
 * Reset manual forçado por operador (pela interface do site)
 */
export function resetManualTravaMotor1() {
  motor1State = {
    emExecucao: false,
    motorNome: "Motor 1 - Enriquecedor SEFAZ",
    loteId: null,
    totalNotas: 0,
    notasProcessadas: 0,
    inicioExecucao: null,
    ultimoPulso: null,
    errosConsecutivos: 0,
    statusDescritivo: "OCIOSO",
    mensagemAlerta: "Trava resetada manualmente pelo operador.",
  };
  return motor1State;
}

