"use client";

import { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { 
  ArrowUpRight, 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  Layers, 
  BadgeCheck, 
  Send, 
  FileCheck2, 
  Sparkles, 
  RefreshCw,
  Receipt,
  FileQuestion,
  Calendar,
  Percent,
  TrendingUp,
  Table
} from "lucide-react";
import Link from "next/link";

interface CompetenciaStats {
  mesAno: string;
  prazoLegal: string;
  statusPrazo: "EM_DIA" | "ALERTA" | "EXPIRADO";
  totalNaBase: number;
  validadosAptosAguardando: number;
  comProblemaInelegivel: number;
  falhaSefazElegivel: number;
  separadosDigitacao: number;
  enviadosSefaz: number;
  rejeitadosPortal: number;
  totalEnriquecidoFaturavel: number;
  pendentesNaBase: number;
  grauAtingimentoPct: number;
  ultimaAtualizacao: string;
}

interface KpiData {
  motor1Enriquecimento: {
    totalEnriquecidoFaturavel: number;
    totalNaBase: number;
    pendentesNaBase: number;
    validadosAptos: number;
    comProblemaInelegivel: number;
    falhaSefazMasElegivel: number;
  };
  competenciasDisponiveis: string[];
  mesSelecionado: string;
  tabelaCompetencias: CompetenciaStats[];
  resumoMes: {
    totalMes: number;
    enriquecidosMes: number;
    faltamMes: number;
    grauAtingimentoPct: number;
  };
  motor2Digitacao: {
    totalConcluidosCobravel: number;
    enviadosSefaz: number;
    confirmadosRelatorio: number;
    rejeitadosPortal: number;
    separadosDigitacao: number;
  };
}

export default function DashboardPage() {
  const [dados, setDados] = useState<KpiData | null>(null);
  const [mesFiltro, setMesFiltro] = useState<string>("TODOS");
  const [loading, setLoading] = useState(true);

  const carregarKpis = async (mes: string = mesFiltro) => {
    try {
      const res = await fetch(`/api/dashboard/kpis?mes=${mes}`);
      if (res.ok) {
        const json = await res.json();
        setDados(json);
      }
    } catch (err) {
      console.error("Erro ao carregar KPIs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarKpis(mesFiltro);
    const interval = setInterval(() => {
      carregarKpis(mesFiltro);
    }, 10000); // Polling a cada 10s
    return () => clearInterval(interval);
  }, [mesFiltro]);

  const m1 = dados?.motor1Enriquecimento;
  const m2 = dados?.motor2Digitacao;
  const mesInfo = dados?.resumoMes;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-[1600px] w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-8">
        {/* CABEÇALHO */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                CONTROLE OPERACIONAL & COBRANÇA
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                EM TEMPO REAL
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mt-2">
              Dashboard de Produção — Projeto Felix
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Acompanhamento oficial para faturamento por cupom enriquecido e digitado no SEFAZ.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => carregarKpis(mesFiltro)}
              className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition"
              title="Atualizar dados"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-400" : ""}`} />
            </button>
            <Link
              href="/gatilhos"
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition shadow-lg shadow-blue-600/20"
            >
              Acessar Gatilhos & Testes
              <ArrowUpRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* 1. SEÇÃO DE COBRANÇA 1: OS 4 CARDS DO MOTOR DE ENRIQUECIMENTO */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                Controle 1: Faturamento Motor de Enriquecimento (Motor 1)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Total Enriquecido Cobrável = Validados e Aptos + Com Problema (Auditados) + Falha SEFAZ (Elegíveis).
              </p>
            </div>

            {/* Filtro por Mês / Competência */}
            <div className="flex items-center gap-2 bg-slate-900 p-1.5 rounded-xl border border-slate-800 text-xs">
              <Calendar className="w-4 h-4 text-slate-400 ml-1.5" />
              <span className="text-slate-400 font-medium">Mês:</span>
              <select
                value={mesFiltro}
                onChange={(e) => setMesFiltro(e.target.value)}
                className="bg-slate-950 text-white border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs font-mono focus:outline-none focus:border-blue-500"
              >
                <option value="TODOS">Todos os Meses</option>
                {dados?.competenciasDisponiveis?.map((comp) => (
                  <option key={comp} value={comp}>
                    {comp}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* OS 4 CARDS EXATOS */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* Card 1: TOTAL EFETIVAMENTE ENRIQUECIDO (FATURÁVEL) */}
            <div className="bg-slate-900/50 border border-purple-500/40 rounded-2xl p-5 flex flex-col justify-between relative overflow-hidden shadow-lg shadow-purple-950/20">
              <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-purple-300 uppercase tracking-wider">
                  CARD 1: TOTAL ENRIQUECIDO
                </span>
                <div className="p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
                  <BadgeCheck className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold tracking-tight text-white">
                    {m1?.totalEnriquecidoFaturavel ?? 0}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/20 border border-purple-500/30 text-purple-300">
                    Faturável
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Auditados ({m1?.pendentesNaBase ?? 0} restantes na base)
                </p>
              </div>
            </div>

            {/* Card 2: Total Validado e Enriquecido */}
            <div className="bg-slate-900/50 border border-emerald-500/30 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                  CARD 2: VALIDADO E ENRIQUECIDO
                </span>
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold tracking-tight text-emerald-400">
                    {m1?.validadosAptos ?? 0}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    Sem CPF (Apto)
                  </span>
                </div>
                <p className="text-xs text-slate-400">Prontos para doação</p>
              </div>
            </div>

            {/* Card 3: Total com Problema */}
            <div className="bg-slate-900/50 border border-rose-500/30 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-rose-400 uppercase tracking-wider">
                  CARD 3: TOTAL COM PROBLEMA
                </span>
                <div className="p-2 bg-rose-500/10 rounded-lg text-rose-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold tracking-tight text-rose-400">
                    {m1?.comProblemaInelegivel ?? 0}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
                    Inelegível
                  </span>
                </div>
                <p className="text-xs text-slate-400">Com CPF no caixa ou expirado</p>
              </div>
            </div>

            {/* Card 4: Total com Erro mas Elegível para Importação */}
            <div className="bg-slate-900/50 border border-amber-500/30 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                  CARD 4: FALHA SEFAZ (ELEGÍVEL)
                </span>
                <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
                  <FileQuestion className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold tracking-tight text-amber-400">
                    {m1?.falhaSefazMasElegivel ?? 0}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400">
                    Chave & DV OK
                  </span>
                </div>
                <p className="text-xs text-slate-400">Vai para o Motor 2 (Digitador)</p>
              </div>
            </div>
          </div>

          {/* BARRA DE GRAU DE ATINGIMENTO DA COMPETÊNCIA SELECIONADA */}
          {mesInfo && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Percent className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    Grau de Atingimento ({mesFiltro === "TODOS" ? "Geral da Base Real" : `Competência ${mesFiltro}`})
                  </span>
                </div>
                <div className="text-xs font-mono text-slate-300">
                  <strong className="text-emerald-400">{mesInfo.enriquecidosMes}</strong> de{" "}
                  <strong>{mesInfo.totalMes}</strong> cupons auditados (Faltam:{" "}
                  <strong className="text-amber-400">{mesInfo.faltamMes}</strong>)
                </div>
              </div>

              <div className="space-y-1">
                <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-800 p-0.5">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 via-blue-500 to-emerald-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, mesInfo.grauAtingimentoPct))}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Progresso do Volume</span>
                  <span className="font-bold text-emerald-400">{mesInfo.grauAtingimentoPct}% Concluído</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 2. NOVA SEÇÃO: TABELA DINÂMICA DE FECHAMENTO POR COMPETÊNCIA (MÊS A MÊS) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Table className="w-5 h-5 text-blue-400" />
                Fechamento por Competência (Meses Elegíveis & Histórico)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Distribuição real dos cupons encontrados na base agrupados por mês de emissão, prazos legais e faturamento.
              </p>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="w-full">
              <table className="w-full text-left text-xs font-sans table-auto">
                <thead className="bg-slate-950/90 border-b border-slate-800 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  <tr>
                    <th className="py-2.5 px-3">Mês</th>
                    <th className="py-2.5 px-2.5">Prazo SEFAZ</th>
                    <th className="py-2.5 px-2.5 text-white">Total Base</th>
                    <th className="py-2.5 px-2.5 text-emerald-400">Aptos (Fila)</th>
                    <th className="py-2.5 px-2.5 text-rose-400">Problema</th>
                    <th className="py-2.5 px-2.5 text-amber-400">Falha SEFAZ</th>
                    <th className="py-2.5 px-2.5 text-purple-300">Em Digitação</th>
                    <th className="py-2.5 px-2.5 text-cyan-300">Enviado SEFAZ</th>
                    <th className="py-2.5 px-2.5 text-rose-300">Rejeitado</th>
                    <th className="py-2.5 px-2.5 text-slate-400">Faltam</th>
                    <th className="py-2.5 px-2.5">Progresso</th>
                    <th className="py-2.5 px-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px] whitespace-nowrap">
                  {dados?.tabelaCompetencias && dados.tabelaCompetencias.length > 0 ? (
                    dados.tabelaCompetencias.map((comp) => {
                      const badgeStatus =
                        comp.statusPrazo === "EXPIRADO"
                          ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                          : comp.statusPrazo === "ALERTA"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";

                      return (
                        <tr key={comp.mesAno} className="hover:bg-slate-800/30 transition">
                          <td className="py-2 px-3 font-bold text-white flex items-center gap-1.5 font-sans">
                            <Calendar className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                            {comp.mesAno}
                          </td>
                          <td className="py-2 px-2.5">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${badgeStatus}`}>
                              {comp.prazoLegal} {comp.statusPrazo === "EXPIRADO" ? "(Expirado)" : ""}
                            </span>
                          </td>
                          <td className="py-2 px-2.5 font-semibold text-white">{comp.totalNaBase}</td>
                          <td className="py-2 px-2.5 text-emerald-400 font-bold">{comp.validadosAptosAguardando}</td>
                          <td className="py-2 px-2.5 text-rose-400 font-bold">{comp.comProblemaInelegivel}</td>
                          <td className="py-2 px-2.5 text-amber-400 font-bold">{comp.falhaSefazElegivel}</td>
                          <td className="py-2 px-2.5 text-purple-300 font-bold bg-purple-500/5">
                            {comp.separadosDigitacao}
                          </td>
                          <td className="py-2 px-2.5 text-cyan-300 font-bold bg-cyan-500/5">
                            {comp.enviadosSefaz}
                          </td>
                          <td className="py-2 px-2.5 text-rose-300 font-bold bg-rose-500/5">
                            {comp.rejeitadosPortal}
                          </td>
                          <td className="py-2 px-2.5 text-slate-400">{comp.pendentesNaBase}</td>
                          <td className="py-2 px-2.5">
                            <div className="flex items-center gap-1.5">
                              <div className="w-12 h-1.5 bg-slate-950 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-500 rounded-full"
                                  style={{ width: `${comp.grauAtingimentoPct}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-slate-300">{comp.grauAtingimentoPct}%</span>
                            </div>
                          </td>
                          <td className="py-2 px-3 text-right font-sans">
                            <button
                              onClick={() => setMesFiltro(comp.mesAno)}
                              className="px-2 py-0.5 text-[10px] font-medium rounded-md bg-slate-800 hover:bg-slate-700 text-blue-400 hover:text-blue-300 transition"
                            >
                              Filtrar
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={12} className="py-6 text-center text-slate-500 font-sans">
                        Nenhuma competência carregada ainda.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 3. SEÇÃO DE COBRANÇA 2: MOTOR DE DIGITAÇÃO / SEFAZ */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Send className="w-5 h-5 text-emerald-400" />
              Controle 2: Cupons Digitados / Concluídos no SEFAZ (Cobrança Motor 2)
            </h3>
            <span className="text-xs text-emerald-400 font-mono bg-emerald-500/10 px-2.5 py-0.5 rounded border border-emerald-500/20">
              Taxa de Conclusão SEFAZ
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Card Total Concluídos SEFAZ */}
            <div className="bg-slate-900/50 border border-emerald-500/30 rounded-2xl p-5 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Concluídos SEFAZ (Cobrável)</span>
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <FileCheck2 className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold tracking-tight text-white">
                    {m2?.totalConcluidosCobravel ?? 0}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    Faturável
                  </span>
                </div>
                <p className="text-xs text-slate-400">Doações efetivadas com sucesso</p>
              </div>
            </div>

            {/* Em Digitação (SEPARADO_DIGITACAO) */}
            <div className="bg-slate-900/50 border border-purple-500/30 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider">Em Digitação (Lote Ativo)</span>
                <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
                  <Layers className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold tracking-tight text-purple-300">
                    {m2?.separadosDigitacao ?? 0}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300">
                    Em lote
                  </span>
                </div>
                <p className="text-xs text-slate-400">Separados pelo Motor 2</p>
              </div>
            </div>

            {/* Enviados ao Portal */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Enviados ao Portal (NFP)</span>
                <div className="p-2 bg-slate-800 rounded-lg text-slate-400">
                  <Send className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <span className="text-3xl font-extrabold tracking-tight text-slate-200">
                  {m2?.enviadosSefaz ?? 0}
                </span>
                <p className="text-xs text-slate-400">Lançados via automação web</p>
              </div>
            </div>

            {/* Confirmados Relatório SEFAZ */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Confirmados Relatório SEFAZ</span>
                <div className="p-2 bg-slate-800 rounded-lg text-slate-400">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <span className="text-3xl font-extrabold tracking-tight text-slate-200">
                  {m2?.confirmadosRelatorio ?? 0}
                </span>
                <p className="text-xs text-slate-400">Reconciliados oficialmente</p>
              </div>
            </div>

            {/* Rejeitados pelo Portal */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Rejeitados pelo Portal</span>
                <div className="p-2 bg-slate-800 rounded-lg text-slate-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 space-y-1">
                <span className="text-3xl font-extrabold tracking-tight text-rose-400">
                  {m2?.rejeitadosPortal ?? 0}
                </span>
                <p className="text-xs text-slate-400">Já cadastrado por outra entidade</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
