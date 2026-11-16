"use client";

import { Navbar } from "@/components/Navbar";
import { 
  Bot, 
  Workflow, 
  CheckCircle2, 
  XCircle, 
  RotateCw, 
  Clock, 
  ShieldCheck, 
  Layers, 
  ArrowRight, 
  Database, 
  Zap, 
  FileSpreadsheet,
  AlertTriangle
} from "lucide-react";

export default function FluxoPage() {
  return (
    <>
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Cabeçalho da Página */}
        <div className="bg-gradient-to-r from-purple-900/30 via-slate-900 to-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 uppercase tracking-wider">
                Arquitetura de Produção
              </span>
              <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 uppercase tracking-wider">
                Status Nativo 100% Intacto
              </span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Fluxo Operacional dos Motores — Projeto Felix
            </h2>
            <p className="text-slate-400 text-sm max-w-3xl">
              Ciclo autônomo com polling a cada 5 minutos, isolamento absoluto na coluna <code className="text-purple-300 font-mono">status_externo</code>, 
              enriquecimento anti-bloqueio e esteira sequencial para o robô digitador.
            </p>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 flex items-center gap-3 shrink-0">
            <Clock className="w-6 h-6 text-purple-400 animate-pulse" />
            <div>
              <div className="text-xs text-slate-400">Loop de Produção</div>
              <div className="text-sm font-bold text-white">A cada 5 minutos (Máx 500 notas)</div>
            </div>
          </div>
        </div>

        {/* 1. Visão Geral da Automação de Produção (O Ciclo do Motor 1) */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <RotateCw className="w-5 h-5 text-purple-400" />
                1. Ciclo Autônomo de Enriquecimento (Passo a Passo da Automação — Para o Fabão)
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                Esteira de processamento contínuo em lotes de 100 cupons. Garante isolamento absoluto: 
                <strong> a coluna nativa <code className="text-emerald-400 font-mono">status</code> do banco parceiro jamais é alterada</strong>, 
                utilizando apenas os campos dedicados da extensão externa.
              </p>
            </div>
            <span className="text-xs font-mono font-semibold px-3 py-1 rounded-lg bg-purple-500/10 text-purple-300 border border-purple-500/20 whitespace-nowrap">
              Lotes de 100 Cupons
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 pt-3">
            {/* PASSO 01 */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2 relative">
              <span className="text-[10px] font-mono text-purple-400 font-bold block">PASSO 01</span>
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-blue-400" /> Ingestão Inteligente
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                O robô consulta a API parceira via <code className="text-slate-300 font-mono">GET /cupons</code> filtrando a fila onde <code className="text-purple-300 font-mono">status_externo IS NULL</code>, coletando lotes de 100 notas virgens.
              </p>
            </div>

            {/* PASSO 02 */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
              <span className="text-[10px] font-mono text-purple-400 font-bold block">PASSO 02</span>
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-400" /> Triagem Legal & Fila
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Extrai o <code className="text-slate-300 font-mono">AAMM</code> da chave. Cupons já vencidos (Agosto ou anterior) recebem descarte imediato como <code className="text-rose-400 font-mono">EXPIRADO</code> (sem gastar SEFAZ). Os vivos são ordenados por urgência (Setembro antes de Outubro).
              </p>
            </div>

            {/* PASSO 03 */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
              <span className="text-[10px] font-mono text-purple-400 font-bold block">PASSO 03</span>
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Auditoria Matemática
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Calcula o Módulo 11 (DV) nos 44 dígitos. Se a chave for autêntica, ela é blindada: mesmo em caso de oscilação da SEFAZ pública, o cupom segue elegível para digitação.
              </p>
            </div>

            {/* PASSO 04 */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
              <span className="text-[10px] font-mono text-purple-400 font-bold block">PASSO 04</span>
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-400" /> Extração SEFAZ
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Consulta a Fazenda SP pública (sem captcha) com delay humano seguro (1.5s a 4s). Extrai Valor (R$), Data de Emissão e audita se há CPF de consumidor no caixa.
              </p>
            </div>

            {/* PASSO 05 */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
              <span className="text-[10px] font-mono text-purple-400 font-bold block">PASSO 05</span>
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-emerald-400" /> Retorno via PATCH
              </h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Grava nota a nota via <code className="text-blue-300 font-mono">PATCH /cupons/:id</code> preenchendo <code className="text-purple-300 font-mono">valor</code>, <code className="text-purple-300 font-mono">data_emissao</code> e <code className="text-emerald-400 font-mono">status_externo</code>.
              </p>
            </div>
          </div>
        </div>

        {/* 2. Diagrama de Transição de Status (Motor 1 vs Motor 2) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Card Motor 1: Enriquecimento */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Bot className="w-5 h-5 text-blue-400" />
                  Motor 1: Enriquecedor SEFAZ
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono font-bold">
                  Execução Web/Cloud
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Responsável por auditar, extrair valor/data, calcular Módulo 11 da chave, checar se tem CPF e atualizar o <code className="text-purple-300 font-mono">status_externo</code> imediatamente.
              </p>

              <div className="space-y-2 pt-2">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <span className="font-mono text-emerald-400 font-semibold">ENRIQUECIDO_APTO</span>
                  <span className="text-slate-400 text-[11px]">Sem CPF | Valor extraído | No prazo</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <span className="font-mono text-blue-400 font-semibold">ENRIQUECIMENTO_FALHOU_CHAVE_OK</span>
                  <span className="text-slate-400 text-[11px]">SEFAZ oscilou, mas Chave e DV OK</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <span className="font-mono text-amber-400 font-semibold">ERRO_ENRIQUECIMENTO</span>
                  <span className="text-slate-400 text-[11px]">Erro temporário (Tenta de novo no próx ciclo)</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <span className="font-mono text-rose-400 font-semibold">INELEGIVEL_CPF / EXPIRADO</span>
                  <span className="text-slate-400 text-[11px]">Rejeição irreversível (Descarte final)</span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Atualiza <code className="text-slate-300">data_processamento_externo</code> a cada nota.
            </div>
          </div>

          {/* Card Motor 2: Robô Digitador */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Workflow className="w-5 h-5 text-emerald-400" />
                  Motor 2: Robô Digitador Portal NFP
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono font-bold">
                  Execução Local / Perfil Salvo
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Consome exclusivamente os cupons preparados pelo Motor 1, garantindo que o portal só receba notas válidas e sem CPF.
              </p>

              <div className="space-y-2 pt-2">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-mono">Entrada de Cupons</span>
                    <span className="font-mono text-slate-200 text-xs font-semibold">
                      ENRIQUECIDO_APTO ou CHAVE_OK
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px]">Aguardando</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-mono">Trava de Concorrência</span>
                    <span className="font-mono text-purple-400 text-xs font-semibold">
                      SEPARADO_DIGITACAO
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 text-[10px]">Em Digitação</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-mono">Submetido no Portal</span>
                    <span className="font-mono text-emerald-400 text-xs font-semibold">
                      ENVIADO_SEFAZ
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px]">Sucesso</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-mono">Rejeição no Portal</span>
                    <span className="font-mono text-rose-400 text-xs font-semibold">
                      REJEITADO_PORTAL
                    </span>
                  </div>
                  <span className="text-slate-400 text-[10px]">{`detalhe_externo: motivo`}</span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              Nenhum dos dois motores altera o campo nativo <code className="text-slate-300 font-mono">status</code> da base.
            </div>
          </div>
        </div>

        {/* 3. Fechamento e Reconciliação Final (Relatório de Pedidos SEFAZ) */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-amber-400" />
              3. Etapa Final de Reconciliação (Conferência do Relatório Oficial da SEFAZ)
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 font-mono">
              Auditoria de Fechamento
            </span>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Posteriormente, ao importar o relatório oficial de pedidos emitido pelo portal da SEFAZ, o sistema confere todas as notas que estavam como <code className="text-emerald-300 font-mono">ENVIADO_SEFAZ</code> e atualiza para:
          </p>

          <div className="p-4 rounded-xl bg-slate-950 border border-emerald-500/30 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
                ✓
              </div>
              <div>
                <h4 className="text-sm font-bold text-emerald-400 font-mono">CONFIRMADO_RELATORIO</h4>
                <p className="text-xs text-slate-400">
                  Comprovação documental de que o cupom foi aceito pela Fazenda e creditado para a organização.
                </p>
              </div>
            </div>
            <span className="text-xs font-semibold px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Ciclo 100% Concluído
            </span>
          </div>
        </div>
      </main>
    </>
  );
}

