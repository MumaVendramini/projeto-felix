"use client";

import { useState, useEffect, useRef } from "react";
import { Navbar } from "@/components/Navbar";
import { TerminalConsole, LogEntry } from "@/components/TerminalConsole";
import { 
  Key, 
  Radio, 
  RefreshCw, 
  Database, 
  Sparkles, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  FileText, 
  ExternalLink, 
  Play, 
  Pause, 
  ShieldCheck, 
  Clock, 
  HeartPulse, 
  Lock, 
  Unlock 
} from "lucide-react";
import { Cupom } from "@/lib/nfp-api";
import { SefazEnrichResult } from "@/lib/sefaz-enricher";
import { analisarChaveNfp, AnaliseChaveNfp } from "@/lib/nfp-chave-validator";

interface CupomComEnriquecimento extends Cupom {
  analiseChave?: AnaliseChaveNfp;
  enriquecido?: SefazEnrichResult;
  enriquecendo?: boolean;
}

export default function GatilhosPage() {
  const [token, setToken] = useState("");
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [cupons, setCupons] = useState<CupomComEnriquecimento[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Estados de Controle de Processamento Seguro em Lote
  const [batchRunning, setBatchRunning] = useState(false);
  const [modoSeguranca, setModoSeguranca] = useState<"aleatorio" | "moderado">("aleatorio");
  const [progressoBatch, setProgressoBatch] = useState<{ atual: number; total: number } | null>(null);
  const pauseRequestedRef = useRef(false);

  // Estado do Heartbeat e Lock do Motor 1
  const [motorState, setMotorState] = useState<{
    emExecucao: boolean;
    statusDescritivo: string;
    segundosSemPulso: number;
    travadoZumbi: boolean;
    errosConsecutivos: number;
    mensagemAlerta?: string | null;
  } | null>(null);

  // Estados do Loop Automático e Timer Regressivo (30 Segundos para Testes)
  const [autoLoopAtivo, setAutoLoopAtivo] = useState(false);
  const INTERVALO_TESTE_SEGUNDOS = 30; // 30 segundos para testes rápidos
  const [segundosRestantes, setSegundosRestantes] = useState(INTERVALO_TESTE_SEGUNDOS);
  const autoLoopRef = useRef(false);

  // Polling leve para sincronizar o status do Heartbeat
  const atualizarStatusMotor = async () => {
    try {
      const res = await fetch("/api/motor/status");
      if (res.ok) {
        const data = await res.json();
        setMotorState(data);
      }
    } catch {}
  };

  useEffect(() => {
    atualizarStatusMotor();
    const interval = setInterval(atualizarStatusMotor, 3000);
    return () => clearInterval(interval);
  }, []);

  // Efeito do Timer Regressivo Inteligente:
  // Só faz a contagem regressiva quando o motor estiver OCIOSO (fora de execução).
  // Durante o enriquecimento do lote, o timer fica pausado mostrando "Processando lote...".
  // Assim que o lote termina, o timer reinicia do zero para esperar o intervalo completo!
  useEffect(() => {
    autoLoopRef.current = autoLoopAtivo;
    if (!autoLoopAtivo) {
      setSegundosRestantes(INTERVALO_TESTE_SEGUNDOS);
      return;
    }

    // Se estiver ocupado enriquecendo ou buscando, NÃO decrementa o timer!
    if (batchRunning || loadingAction) {
      return;
    }

    const timer = setInterval(() => {
      setSegundosRestantes((prev) => {
        if (prev <= 1) {
          // Quando o timer zera e o motor está ocioso, dispara o ciclo
          if (autoLoopRef.current && !batchRunning && !loadingAction) {
            handleCicloAutomatico();
          }
          return INTERVALO_TESTE_SEGUNDOS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [autoLoopAtivo, batchRunning, loadingAction]);

  // Inicializa logs e carrega token apenas no cliente (evita React Hydration Error)
  useEffect(() => {
    setLogs([
      {
        timestamp: new Date().toLocaleTimeString("pt-BR"),
        type: "info",
        message: "Console inicializado. Token carregado por padrão do ambiente (.env.local) ou insira abaixo.",
      },
    ]);

    const salvo = localStorage.getItem("nfp_api_token");
    if (salvo) setToken(salvo);
  }, []);

  const handleTokenChange = (val: string) => {
    setToken(val);
    localStorage.setItem("nfp_api_token", val);
  };

  const addLog = (type: LogEntry["type"], message: string) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date().toLocaleTimeString("pt-BR"),
        type,
        message,
      },
    ]);
  };

  const handleTrigger = async (action: string) => {
    setLoadingAction(action);
    addLog("info", `Disparando gatilho: [${action}]...`);

    try {
      const res = await fetch("/api/triggers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, token: token.trim(), limite: 100 }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Falha na resposta do servidor.");
      }

      addLog("success", `[${action}] Sucesso: ${data.message}`);

      if (action === "fetch_cupons" && data.itens) {
        // Analisa e classifica cada chave matematicamente e por prazo legal
        const itensComAnalise: CupomComEnriquecimento[] = data.itens.map((c: Cupom) => {
          const payload = c.chave || c.url_consulta || "";
          const analise = analisarChaveNfp(payload);
          return {
            ...c,
            analiseChave: analise,
          };
        });

        // Ordena por prioridade: URGENTE primeiro -> MODERADA -> TRANQUILA -> EXPIRADO
        const ordemUrgencia: Record<string, number> = {
          URGENTE: 1,
          MODERADA: 2,
          TRANQUILA: 3,
          EXPIRADO: 4,
        };

        itensComAnalise.sort((a, b) => {
          const prioridadeA = ordemUrgencia[a.analiseChave?.urgencia || "TRANQUILA"];
          const prioridadeB = ordemUrgencia[b.analiseChave?.urgencia || "TRANQUILA"];
          if (prioridadeA !== prioridadeB) {
            return prioridadeA - prioridadeB;
          }
          return (a.analiseChave?.diasParaVencer ?? 999) - (b.analiseChave?.diasParaVencer ?? 999);
        });

        setCupons(itensComAnalise);
        itensComAnalise.forEach((c) => {
          const an = c.analiseChave;
          addLog(
            an?.expirado ? "warn" : "info",
            `Cupom #${c.id} carregado | Limite: ${an?.dataLimiteFormatada} | Urgência: ${an?.urgencia} | DV: ${an?.dvValido ? "OK" : "INVÁLIDO"}`
          );
        });
      }
    } catch (err: any) {
      addLog("error", `Falha no gatilho [${action}]: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  // Função auxiliar de espera (Delay)
  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  // Enriquecer lista de cupons com Segurança Anti-Bloqueio, Lock e Heartbeat
  const handleStartBatch = async (listaCustomizada?: CupomComEnriquecimento[]) => {
    const listaAlvo = listaCustomizada || cupons;
    const pendentes = listaAlvo.filter((c) => !c.enriquecido);
    if (pendentes.length === 0) {
      addLog("warn", "Todos os cupons da lista já foram enriquecidos!");
      return;
    }

    // 1. Tenta Adquirir a Trava (Lock)
    try {
      const lockRes = await fetch("/api/motor/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acao: "adquirir", totalNotas: pendentes.length }),
      });
      const lockData = await lockRes.json();
      if (!lockRes.ok) {
        addLog("error", `[TRAVA NEGADA] ${lockData.error}`);
        return;
      }
      addLog("success", "[LOCK ATIVO] Trava do Motor 1 adquirida com exclusividade.");
    } catch (e: any) {
      addLog("error", `Falha ao solicitar trava: ${e.message}`);
      return;
    }

    setBatchRunning(true);
    pauseRequestedRef.current = false;
    setProgressoBatch({ atual: 0, total: pendentes.length });

    addLog(
      "info",
      `Iniciando lote seguro para ${pendentes.length} cupons no Modo: ${
        modoSeguranca === "aleatorio" ? "Aleatório (1.5s - 4.0s)" : "Moderado (2.0s fixo)"
      }`
    );

    for (let i = 0; i < pendentes.length; i++) {
      if (pauseRequestedRef.current) {
        addLog("warn", "Processamento em lote PAUSADO pelo operador.");
        break;
      }

      const cupom = pendentes[i];
      setProgressoBatch({ atual: i + 1, total: pendentes.length });

      // Executa a consulta passando o objeto do cupom diretamente
      await handleEnriquecerCupom(cupom.id, cupom);

      // 2. Emite o Pulso de Vida (Heartbeat) & Checa Circuit Breaker
      try {
        const pulsoRes = await fetch("/api/motor/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ acao: "pulso", sucessoNota: true }),
        });
        const pulsoData = await pulsoRes.json();
        if (pulsoData.desarmarLote) {
          addLog("error", `[CIRCUIT BREAKER] ${pulsoData.motivo}`);
          break;
        }
      } catch {}

      // Aplica intervalo de segurança se não for o último
      if (i < pendentes.length - 1 && !pauseRequestedRef.current) {
        let delayMs = 2000; // Moderado: 2.0s
        if (modoSeguranca === "aleatorio") {
          delayMs = Math.floor(Math.random() * (4000 - 1500 + 1)) + 1500;
        }

        const delaySec = (delayMs / 1000).toFixed(1);
        addLog("info", `[Anti-Bloqueio SEFAZ] Aguardando ${delaySec}s antes do próximo cupom...`);
        await sleep(delayMs);
      }
    }

    // 3. Libera a Trava ao concluir
    try {
      await fetch("/api/motor/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acao: "liberar" }),
      });
      addLog("info", "[LOCK LIBERADO] Trava do Motor 1 liberada.");
    } catch {}

    setBatchRunning(false);
    pauseRequestedRef.current = false;
    atualizarStatusMotor();
    setSegundosRestantes(INTERVALO_TESTE_SEGUNDOS); // Reinicia o timer para os 30s completos APÓS terminar o lote!
    addLog("success", "Fim da execução do lote.");
  };

  // Função do Ciclo Automático: busca e já passa os cupons diretamente para o enriquecimento
  const handleCicloAutomatico = async () => {
    addLog("info", "[CICLO AUTOMÁTICO] Buscando cupons pendentes...");
    try {
      const res = await fetch("/api/triggers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "fetch_cupons", token: token.trim(), limite: 100 }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Falha ao buscar cupons.");
      }

      if (data.itens && data.itens.length > 0) {
        const itensComAnalise: CupomComEnriquecimento[] = data.itens.map((c: Cupom) => {
          const payload = c.chave || c.url_consulta || "";
          return {
            ...c,
            analiseChave: analisarChaveNfp(payload),
          };
        });

        setCupons(itensComAnalise);
        addLog("success", `[CICLO AUTOMÁTICO] ${itensComAnalise.length} cupons carregados. Disparando enriquecimento imediato...`);
        
        // Dispara o enriquecimento passando a lista recém-carregada diretamente
        await handleStartBatch(itensComAnalise);
      } else {
        addLog("info", "[CICLO AUTOMÁTICO] Fila vazia na API Gestão NFP. Aguardando próximo ciclo de 1m.");
      }
    } catch (err: any) {
      addLog("error", `Erro no ciclo automático: ${err.message}`);
    }
  };

  const handlePauseBatch = () => {
    pauseRequestedRef.current = true;
    addLog("warn", "Solicitação de pausa enviada. Aguardando a consulta atual terminar...");
  };

  const handleResetManualTrava = async () => {
    try {
      const res = await fetch("/api/motor/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acao: "reset_manual" }),
      });
      const data = await res.json();
      atualizarStatusMotor();
      addLog("warn", "[RESET MANUAL] Trava do Motor 1 foi resetada forçadamente.");
    } catch (e: any) {
      addLog("error", `Erro ao resetar trava: ${e.message}`);
    }
  };

  // Enriquecer um cupom individualmente
  const handleEnriquecerCupom = async (
    cupomId: number, 
    cupomObj?: CupomComEnriquecimento
  ) => {
    const alvo = cupomObj || cupons.find((c) => c.id === cupomId);
    if (!alvo) return;

    const payload = alvo.url_consulta || alvo.chave;
    if (!payload) {
      addLog("error", `Cupom #${cupomId} não tem nem URL nem Chave para consulta.`);
      return;
    }

    // Trava de Prazo Legal Imediata: se já estiver expirado na chave, não chama a SEFAZ
    const analise = alvo.analiseChave || analisarChaveNfp(payload);
    if (analise.expirado) {
      addLog("warn", `[EXPIRADO] Cupom #${cupomId} com prazo expirado em ${analise.dataLimiteFormatada}. Gravando descarte auditado...`);
      try {
        await fetch("/api/triggers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "patch_externo",
            token: token.trim(),
            cupomId,
            payloadExterno: {
              status_externo: "EXPIRADO",
              detalhe_externo: `Prazo legal de doação expirou em ${analise.dataLimiteFormatada}`,
              data_processamento_externo: new Date().toISOString(),
            },
          }),
        });
        setCupons((prev) =>
          prev.map((c) =>
            c.id === cupomId
              ? {
                  ...c,
                  status_externo: "EXPIRADO",
                  detalhe_externo: `Prazo expirou em ${analise.dataLimiteFormatada}`,
                  enriquecido: {
                    sucesso: false,
                    mensagem: `Prazo expirou em ${analise.dataLimiteFormatada}`,
                    temCpf: false,
                    chaveValida: analise.dvValido,
                    valor: null,
                    dataEmissao: null,
                    cnpjEmitente: null,
                    statusSefaz: "EXPIRADO_LEGALMENTE",
                    urlUsada: payload,
                  },
                  enriquecendo: false,
                }
              : c
          )
        );
        addLog("info", `[DB PARCEIRO] Cupom #${cupomId} registrado como EXPIRADO (Faturável no Card 3 - Problema).`);
      } catch (err: any) {
        addLog("error", `Erro ao salvar status de expirado do cupom #${cupomId}: ${err.message}`);
      }
      return;
    }

    setCupons((prev) =>
      prev.map((c) => (c.id === cupomId ? { ...c, enriquecendo: true } : c))
    );

    addLog("info", `Consultando SEFAZ SP para cupom #${cupomId}...`);

    try {
      const res = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urlOuChave: payload }),
      });

      const resultado: SefazEnrichResult = await res.json();

      setCupons((prev) =>
        prev.map((c) =>
          c.id === cupomId ? { ...c, enriquecido: resultado, enriquecendo: false } : c
        )
      );

      if (resultado.sucesso) {
        const cpfStatus = resultado.temCpf
          ? `COM CPF (${resultado.cpfConsumidor || "identificado"})`
          : "SEM CPF (Apto para doação)";
        addLog(
          "success",
          `Cupom #${cupomId} Enriquecido! Valor: ${resultado.valorFormatado ?? "N/D"} | Data: ${resultado.dataEmissao ?? "N/D"} | Consumidor: ${cpfStatus}`
        );

        // Dispara a gravação no banco da API (PATCH)
        const statusParaGravar = resultado.temCpf ? "INELEGIVEL_CPF" : "ENRIQUECIDO_APTO";
        const detalheParaGravar = resultado.temCpf ? "Consumidor cadastrou CPF no caixa" : null;

        // Formata a data de emissão para o formato padrão do banco (AAAA-MM-DD)
        let dataEmissaoFormatada: string | null = null;
        if (resultado.dataEmissao) {
          // Converte DD/MM/AAAA para AAAA-MM-DD
          const partes = resultado.dataEmissao.split("/");
          if (partes.length === 3) {
            dataEmissaoFormatada = `${partes[2]}-${partes[1]}-${partes[0]}`;
          }
        }

        try {
          const patchRes = await fetch("/api/triggers", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: "patch_externo",
              token: token.trim(),
              cupomId,
              payloadExterno: {
                status_externo: statusParaGravar,
                detalhe_externo: detalheParaGravar,
                data_processamento_externo: new Date().toISOString(),
                valor: resultado.valor,
                data_emissao: dataEmissaoFormatada,
              },
            }),
          });
          const patchData = await patchRes.json();
          if (patchRes.ok) {
            addLog("success", `[DB PARCEIRO] Cupom #${cupomId} atualizado no banco com status_externo = "${statusParaGravar}"!`);
            // Atualiza o estado visual do cupom com o status_externo persistido
            setCupons((prev) =>
              prev.map((c) =>
                c.id === cupomId
                  ? { ...c, status_externo: statusParaGravar, detalhe_externo: detalheParaGravar }
                  : c
              )
            );
          } else {
            addLog("error", `Falha ao gravar no DB do parceiro: ${patchData.error}`);
          }
        } catch (dbErr: any) {
          addLog("error", `Erro de conexão ao gravar no DB: ${dbErr.message}`);
        }
      } else {
        addLog("warn", `Cupom #${cupomId} retorno SEFAZ: ${resultado.mensagem}`);

        // Grava o erro de enriquecimento no banco
        const dvValido = alvo.analiseChave?.dvValido ?? false;
        const statusErro = dvValido ? "ENRIQUECIMENTO_FALHOU_CHAVE_OK" : "ERRO_ENRIQUECIMENTO";
        try {
          await fetch("/api/triggers", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: "patch_externo",
              token: token.trim(),
              cupomId,
              payloadExterno: {
                status_externo: statusErro,
                detalhe_externo: resultado.mensagem || "Falha na consulta SEFAZ",
                data_processamento_externo: new Date().toISOString(),
              },
            }),
          });
          addLog("info", `[DB PARCEIRO] Cupom #${cupomId} registrado com status_externo = "${statusErro}".`);
        } catch {}
      }
    } catch (err: any) {
      addLog("error", `Erro ao enriquecer Cupom #${cupomId}: ${err.message}`);
      setCupons((prev) =>
        prev.map((c) => (c.id === cupomId ? { ...c, enriquecendo: false } : c))
      );
    }
  };

  return (
    <>
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Radio className="w-5 h-5 text-blue-400" />
            Painel de Gatilhos & Testes Operacionais
          </h2>
          <p className="text-slate-400 text-sm">
            Execute testes controlados na fila da API, enriqueça os dados na SEFAZ e audite a presença de CPF.
          </p>
        </div>

        {/* Card de Saúde do Motor 1 (Lock & Heartbeat) */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center border ${
              motorState?.emExecucao 
                ? "bg-purple-500/20 border-purple-500/40 text-purple-400" 
                : "bg-slate-800 border-slate-700 text-slate-400"
            }`}>
              <HeartPulse className={`w-5 h-5 ${motorState?.emExecucao ? "animate-pulse text-purple-400" : ""}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-white">Saúde do Motor 1 (Enriquecimento)</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                  motorState?.emExecucao
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 font-bold"
                    : "bg-slate-800 text-slate-400 border-slate-700"
                }`}>
                  {motorState?.statusDescritivo || "OCIOSO"}
                </span>
                {motorState?.travadoZumbi && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-bounce">
                    ZUMBI DETECTADO
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400">
                {motorState?.emExecucao 
                  ? `Em execução ativa • Último pulso há ${motorState.segundosSemPulso}s`
                  : "Nenhum processo travado • Pronto para novo ciclo"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Botão de Ativação do Loop Automático com Timer */}
            <button
              onClick={() => {
                const novo = !autoLoopAtivo;
                setAutoLoopAtivo(novo);
                addLog(novo ? "success" : "warn", novo 
                  ? `[LOOP ATIVO] Automação contínua iniciada. Próximo disparo em 30s.`
                  : `[LOOP PAUSADO] Automação contínua desativada.`);
              }}
              className={`text-xs px-3 py-1.5 rounded-lg border font-semibold flex items-center gap-1.5 transition-all shadow-sm ${
                autoLoopAtivo
                  ? "bg-emerald-600 hover:bg-emerald-500 border-emerald-500 text-white shadow-emerald-600/20"
                  : "bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300"
              }`}
            >
              {autoLoopAtivo ? (
                <>
                  <Pause className="w-3.5 h-3.5 fill-current" />
                  {batchRunning ? (
                    <span className="animate-pulse">Enriquecendo Lote...</span>
                  ) : (
                    <span>Próximo ciclo ({String(Math.floor(segundosRestantes / 60)).padStart(2, "0")}:{String(segundosRestantes % 60).padStart(2, "0")})</span>
                  )}
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current text-emerald-400" />
                  Iniciar Loop Contínuo (30s)
                </>
              )}
            </button>

            <button
              onClick={handleResetManualTrava}
              className="text-xs px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors"
              title="Libera a trava forçadamente se o processo travou"
            >
              <Unlock className="w-3.5 h-3.5 text-amber-400" />
              Resetar Trava
            </button>
          </div>
        </div>

        {/* Linha Superior: Controles e Console */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Coluna da Esquerda: Gatilhos */}
          <div className="lg:col-span-5 space-y-4">
            {/* Bloco de Credencial */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-blue-400" />
                  Token da API Gestão NFP
                </label>
                <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                  Salvo automaticamente
                </span>
              </div>
              <input
                type="password"
                value={token}
                onChange={(e) => handleTokenChange(e.target.value)}
                placeholder="Configurado no .env.local ou cole aqui..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 font-mono transition-colors"
              />
              <p className="text-[11px] text-slate-500">
                O token fica persistido no seu navegador e no servidor local via <code className="text-slate-400">.env.local</code>.
              </p>
            </div>

            {/* Ações de Gatilho */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-2">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Gatilhos Disponíveis
              </span>

              <button
                onClick={() => handleTrigger("test_connection")}
                disabled={loadingAction !== null}
                className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 text-slate-200 text-xs font-medium transition-all disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  <RefreshCw className={`w-4 h-4 text-blue-400 ${loadingAction === "test_connection" ? "animate-spin" : ""}`} />
                  Testar Conexão com API
                </span>
                <span className="text-[10px] text-slate-400">Status 200</span>
              </button>

              <button
                onClick={() => handleTrigger("fetch_cupons")}
                disabled={loadingAction !== null || batchRunning}
                className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 text-slate-200 text-xs font-medium transition-all disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  <Database className={`w-4 h-4 text-emerald-400 ${loadingAction === "fetch_cupons" ? "animate-spin" : ""}`} />
                  Buscar Próximos 100 Cupons
                </span>
                <span className="text-[10px] text-slate-400">GET /cupons (100)</span>
              </button>

              {/* Bloco de Enriquecimento Seguro em Lote */}
              <div className="pt-2 border-t border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                    Enriquecimento Anti-Bloqueio
                  </span>
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      onClick={() => setModoSeguranca("aleatorio")}
                      disabled={batchRunning}
                      className={`text-[10px] px-2 py-0.5 rounded font-medium transition-all ${
                        modoSeguranca === "aleatorio"
                          ? "bg-purple-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Aleatório (1.5s - 4s)
                    </button>
                    <button
                      onClick={() => setModoSeguranca("moderado")}
                      disabled={batchRunning}
                      className={`text-[10px] px-2 py-0.5 rounded font-medium transition-all ${
                        modoSeguranca === "moderado"
                          ? "bg-blue-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Moderado (2s)
                    </button>
                  </div>
                </div>

                {!batchRunning ? (
                  <button
                    onClick={() => handleStartBatch()}
                    disabled={cupons.length === 0}
                    className="w-full flex items-center justify-center gap-2 p-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-all disabled:opacity-40"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Iniciar Lote Seguro ({cupons.filter((c) => !c.enriquecido).length} pendentes)
                  </button>
                ) : (
                  <button
                    onClick={handlePauseBatch}
                    className="w-full flex items-center justify-center gap-2 p-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-lg shadow-amber-600/20 transition-all"
                  >
                    <Pause className="w-3.5 h-3.5 fill-current" />
                    Pausar Processamento ({progressoBatch?.atual}/{progressoBatch?.total})
                  </button>
                )}

                {/* Barra de Progresso do Lote */}
                {progressoBatch && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                      <span>Progresso do Lote</span>
                      <span>
                        {progressoBatch.atual} / {progressoBatch.total} notas (
                        {Math.round((progressoBatch.atual / progressoBatch.total) * 100)}%)
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                      <div
                        className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-300"
                        style={{
                          width: `${(progressoBatch.atual / progressoBatch.total) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Coluna da Direita: Mini Terminal Console */}
          <div className="lg:col-span-7">
            <TerminalConsole logs={logs} onClear={() => setLogs([])} />
          </div>
        </div>

        {/* Linha Inferior: Tabela Visual de Cupons Antes x Depois */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                Auditoria Visual: Cupons na Fila (Antes x Pós-Enriquecimento)
              </h3>
              <p className="text-xs text-slate-400">
                Observe o valor e a data vindos como <code className="text-amber-300 font-mono">null</code> da API e veja-os preenchidos após a consulta SEFAZ.
              </p>
            </div>
            {cupons.length > 0 && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-mono">
                {cupons.length} cupons carregados
              </span>
            )}
          </div>

          {cupons.length === 0 ? (
            <div className="border border-dashed border-slate-800 rounded-xl p-8 text-center text-slate-500 text-xs">
              Nenhum cupom carregado na memória. Clique em <strong className="text-slate-300">"Buscar Próximos 5 Cupons"</strong> acima para carregar a fila.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] font-semibold tracking-wider">
                    <th className="py-3 px-3">ID / Org</th>
                    <th className="py-3 px-3">Chave / Origem</th>
                    <th className="py-3 px-3">Prazo Legal (Prioridade)</th>
                    <th className="py-3 px-3">Valor (Antes x Depois)</th>
                    <th className="py-3 px-3">Data Emissão</th>
                    <th className="py-3 px-3">Consumidor (CPF)</th>
                    <th className="py-3 px-3">Status SEFAZ</th>
                    <th className="py-3 px-3">Status Externo (DB)</th>
                    <th className="py-3 px-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {cupons.map((c) => {
                    const enr = c.enriquecido;
                    const an = c.analiseChave;
                    return (
                      <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-3 font-mono">
                          <span className="text-blue-400 font-bold">#{c.id}</span>
                          <div className="text-[10px] text-slate-500">{c.cnpj_organizacao}</div>
                        </td>

                        <td className="py-3 px-3 max-w-[220px]">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate font-mono text-slate-300" title={c.chave || ""}>
                              {c.chave ? c.chave.slice(0, 20) + "..." : "Sem chave"}
                            </span>
                            {/* Link direto para consulta manual na SEFAZ SP */}
                            {(c.url_consulta || c.chave) && (
                              <a
                                href={
                                  c.url_consulta ||
                                  `https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p=${c.chave}|1|1|1|1`
                                }
                                target="_blank"
                                rel="noreferrer"
                                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-blue-400 hover:text-blue-300 transition-colors inline-flex items-center"
                                title="Abrir consulta pública oficial na SEFAZ SP (nova aba)"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </a>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-slate-500">
                              {c.url_consulta ? "Origem: QR Code" : "Origem: Chave 44d"}
                            </span>
                            {an && (
                              <span
                                className={`text-[9px] font-mono px-1 rounded ${
                                  an.dvValido
                                    ? "text-emerald-400 bg-emerald-500/10"
                                    : "text-rose-400 bg-rose-500/10"
                                }`}
                                title={`DV Informado: ${an.dvInformado} | Calculado: ${an.dvCalculado}`}
                              >
                                {an.dvValido ? "DV OK" : "DV INVÁLIDO"}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Coluna Prazo Legal & Urgência */}
                        <td className="py-3 px-3">
                          {an ? (
                            <div className="flex flex-col">
                              <span className="font-mono text-xs text-slate-200">
                                {an.dataLimiteFormatada}
                              </span>
                              {an.urgencia === "URGENTE" && (
                                <span className="inline-flex items-center gap-1 text-[10px] text-rose-400 font-bold">
                                  🔥 Vence em {an.diasParaVencer}d
                                </span>
                              )}
                              {an.urgencia === "MODERADA" && (
                                <span className="text-[10px] text-amber-400 font-medium">
                                  🟡 Vence em {an.diasParaVencer}d
                                </span>
                              )}
                              {an.urgencia === "TRANQUILA" && (
                                <span className="text-[10px] text-emerald-400">
                                  🟢 Vence em {an.diasParaVencer}d
                                </span>
                              )}
                              {an.urgencia === "EXPIRADO" && (
                                <span className="text-[10px] text-slate-500 line-through">
                                  ❌ Expirado
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-500 text-[10px]">-</span>
                          )}
                        </td>

                        {/* Coluna Valor: Antes x Depois */}
                        <td className="py-3 px-3">
                          {enr ? (
                            <div className="flex flex-col">
                              <span className="font-semibold text-emerald-400 text-sm">
                                {enr.valorFormatado || "R$ 0,00"}
                              </span>
                              <span className="text-[10px] text-slate-500 line-through">
                                antes: null
                              </span>
                            </div>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 font-mono text-[11px]">
                              null (aguardando)
                            </span>
                          )}
                        </td>

                        {/* Coluna Data: Antes x Depois */}
                        <td className="py-3 px-3">
                          {enr ? (
                            <div className="flex flex-col">
                              <span className="text-slate-200 font-medium">
                                {enr.dataEmissao || "Não identificada"}
                              </span>
                              <span className="text-[10px] text-slate-500 line-through">
                                antes: null
                              </span>
                            </div>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 font-mono text-[11px]">
                              null
                            </span>
                          )}
                        </td>

                        {/* Coluna Tem CPF? */}
                        <td className="py-3 px-3">
                          {enr ? (
                            enr.temCpf ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[10px] font-semibold">
                                <XCircle className="w-3 h-3" />
                                Com CPF ({enr.cpfConsumidor || "identificado"})
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-semibold">
                                <CheckCircle2 className="w-3 h-3" />
                                Sem CPF (Apto)
                              </span>
                            )
                          ) : (
                            <span className="text-slate-500 text-[11px] italic">Não consultado</span>
                          )}
                        </td>

                        {/* Coluna Status SEFAZ */}
                        <td className="py-3 px-3">
                          {enr ? (
                            enr.sucesso ? (
                              <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {enr.statusSefaz}
                              </span>
                            ) : (
                              <div className="flex flex-col">
                                <span className="inline-flex items-center gap-1 text-rose-400 font-semibold text-[11px]">
                                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                                  {enr.statusSefaz}
                                </span>
                                <span className="text-[10px] text-rose-500 max-w-[200px] truncate" title={enr.mensagem || ""}>
                                  {enr.mensagem}
                                </span>
                              </div>
                            )
                          ) : (
                            <span className="text-slate-500">-</span>
                          )}
                        </td>

                        {/* Coluna Status Externo Persistido no Banco */}
                        <td className="py-3 px-3">
                          {c.status_externo ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 font-mono text-[10px] font-bold">
                              {c.status_externo}
                            </span>
                          ) : (
                            <span className="text-slate-600 font-mono text-[10px]">null (não gravado)</span>
                          )}
                        </td>

                        {/* Botão de Enriquecer */}
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => handleEnriquecerCupom(c.id)}
                            disabled={c.enriquecendo}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-400 hover:text-blue-300 text-xs font-medium transition-colors disabled:opacity-50"
                          >
                            <Sparkles className={`w-3.5 h-3.5 ${c.enriquecendo ? "animate-spin" : ""}`} />
                            {c.enriquecendo ? "Consultando..." : enr ? "Reconsultar" : "Enriquecer"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
