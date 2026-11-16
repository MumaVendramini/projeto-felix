# Projeto Felix — Gestão, Auditoria e Enriquecimento de Cupons NFP

Sistema web serverless de alta performance desenvolvido para orquestrar o ciclo completo de cupons fiscais da **Nota Fiscal Paulista (NFP)** voltados à doação para entidades sociais parceiras.

A solução integra-se à **API Gestão NFP**, audita a fila em tempo real, enriquece dados diretamente na **SEFAZ SP pública** (sem captcha) e prepara o ecossistema com proteção anti-bloqueio (WAF/F5), priorização por prazo legal e controles operacionais em tempo real.

---

## 1. Entendimento do Projeto e Proposta de Valor

### O Desafio
As organizações recebem doações de cupons físicos ou escaneados em urnas que chegam com informações incompletas à fila (muitas vezes apenas a chave de 44 dígitos ou a URL de QR Code, com `valor = null` e `data_emissao = null`). Além disso:
- **Janela Legal Rígida da SEFAZ SP:** Um cupom fiscal só pode ser doado até o **dia 20 do segundo mês subsequente à emissão** (ex: emitido em 13/11/2026 $\rightarrow$ limite de envio 20/01/2027; emitido em 30/09/2026 $\rightarrow$ limite de envio 20/11/2026). Notas vencidas são descarte e geram prejuízo se consumirem esforço da esteira.
- **Independência da Doação vs Enriquecimento:** Embora o enriquecimento sirva para auditar valor, data e checagem de CPF, **a doação no portal da NFP exige apenas a Chave de Acesso com Dígito Verificador (DV Módulo 11) autêntico**. Mesmo que a consulta pública da SEFAZ oscile, o cupom com chave válida permanece apto para doação.
- **Inelegibilidade por CPF:** Se o consumidor informou seu próprio CPF no caixa, a nota torna-se inelegível para doação.
- Consultas em massa à SEFAZ geram bloqueios de IP (WAF/F5) se não forem cadenciadas com comportamento humano.
- A operação precisa de visibilidade e reconciliação entre o que foi enviado e o que foi efetivamente confirmado pelo relatório oficial da SEFAZ.

### A Solução (Projeto Felix)
O Projeto Felix resolve esses gargalos unificando:
1. **Priorização por Janela Legal (Deadline First / Prazo até dia 20):**
   - Extrai instantaneamente o Ano e Mês de Emissão (`AAMM`) embutidos na chave de 44 dígitos.
   - Ordena a esteira dando **prioridade máxima para as notas mais antigas prestes a vencer** no próximo dia 20 (ex: Setembro antes de Outubro).
   - Identifica e descarta cupons legalmente expirados antes de qualquer chamada externa.
2. **Validação Matemática Imediata (Módulo 11):** Validação dos pesos 2 a 9 da SEFAZ, garantindo que cupons com chave válida nunca sejam descartados caso a SEFAZ pública oscile.
3. **Filtro Inteligente de Exclusão:** Cupons que já foram processados ou marcados com `ENRIQUECIMENTO_FALHOU_CHAVE_OK` não são reprocessados em loop, avançando a esteira continuamente.
4. **Auditoria Visual "Antes x Depois":** Exibe o estado bruto recebido da API (`null`) e o estado enriquecido (`R$ 60,64`, data da nota e badge de consumidor).
5. **Triagem de Elegibilidade Fiscal (Sem CPF):** Identifica se o cupom tem `Consumidor não identificado` (apto para doação à entidade) ou se já possui CPF registrado (rejeição imediata).
6. **Mecanismo Anti-Bloqueio SEFAZ (Safe Crawling):** Modos com jitter aleatório (1.5s a 4.0s), controle de pausa a quente e fila sequencial.
7. **Fechamento e Histórico por Competência:** Tabela com visualização dinâmica dos meses elegíveis, cálculo de prazo legal, % de atingimento e persistência em `historico_competencias.json`.
8. **Máquina de Estados & Reconciliação (Campos Dedicados):** Rastreamento do ciclo completo sem interferir nas colunas nativas do banco parceiro:
   - **`status_externo`** (`VARCHAR(50)`): `PENDENTE_ENRIQUECIMENTO` $\rightarrow$ `ENRIQUECIDO_APTO` $\rightarrow$ `SEPARADO_DIGITACAO` $\rightarrow$ `ENVIADO_SEFAZ` $\rightarrow$ `CONFIRMADO_RELATORIO` (ou `INELEGIVEL_CPF`, `EXPIRADO`, `ENRIQUECIMENTO_FALHOU_CHAVE_OK`, `ERRO_ENRIQUECIMENTO`).
   - **`detalhe_externo`** (`VARCHAR(255)`): Reservado exclusivamente para motivos de erro ou rejeição (ex: *"Consumidor cadastrou CPF no caixa"*, *"QR Code sem parâmetros suportados"*, *"Prazo expirado em 20/10/2026"*).
   - **`data_processamento_externo`** (`TIMESTAMP`): Registro de auditoria do momento exato do processamento.

---

## 2. Documentação Técnica para a Equipe de Dados / Fabão (DBA)

Esta seção foi elaborada especificamente para alinhamento com o **Fabão**, detalhando como o **Projeto Felix** orquestra o ciclo de enriquecimento em total harmonia e segurança com o banco de dados da API Gestão NFP.

### 🛡️ Princípio Fundamental: Isolamento Absoluto do Banco Nativo
* **A coluna nativa `status` NUNCA é alterada pelo Projeto Felix.** Ela permanece sob controle exclusivo da esteira do Fabão (`status: "processamento_urna"`).
* Toda a inteligência de auditoria e enriquecimento é gravada exclusivamente nas colunas dedicadas da extensão:
  - `status_externo` (`VARCHAR(50)`)
  - `detalhe_externo` (`VARCHAR(255)`)
  - `data_processamento_externo` (`TIMESTAMP`)
  - `valor` (`NUMERIC(10,2)`)
  - `data_emissao` (`DATE` / `AAAA-MM-DD`)

---

### ⚙️ O Passo a Passo da Automação (Ciclo do Motor 1)

O motor opera em segundo plano (background daemon / cron) em lotes configurados de **100 cupons por ciclo**:

```text
[Banco Gestão NFP] 
       │
       ▼ (Passo 1: Ingestão Inteligente)
  GET /cupons?limite=100 (filtra status_externo IS NULL)
       │
       ▼ (Passo 2: Triagem Legal & Priorização - Deadline First)
  Identifica AAMM na Chave ───► Se Vencido (Agosto/26 ou anterior) ──► PATCH status_externo = "EXPIRADO" (Sem chamar SEFAZ)
       │
       ├─► Se Vivo: Ordena por Urgência (Setembro/26 vence 20/11 ──► PRIORIDADE MÁXIMA)
       │
       ▼ (Passo 3: Auditoria Matemática de Integridade)
  Cálculo do Módulo 11 (DV) nos 44 dígitos da chave de acesso
       │
       ▼ (Passo 4: Consulta Pública SEFAZ SP sem Captcha)
  Jitter Humano Seguro (1.5s a 4s) contra bloqueio de WAF/F5
  Extrai: Valor Total (R$), Data de Emissão (AAAA-MM-DD) e Checagem de CPF
       │
       ├─► Se CPF identificado no caixa ───────► Inelegível para doação
       └─► Se Consumidor não identificado ────► Apto para doação à entidade
       │
       ▼ (Passo 5: Retorno Transacional Isolado)
  PATCH /cupons/:id com payload estruturado
       │
       ▼
[Banco Gestão NFP Atualizado] (status nativo continua intacto para o Motor 2 - Digitador)
```

#### Detalhamento das 5 Etapas:

1. **Passo 1 — Ingestão com Filtro Inverso Inteligente:**
   * Consulta `GET /cupons?status=processamento_urna&limite=100`.
   * Filtra somente os cupons virgens da esteira externa (`status_externo IS NULL`), ignorando quem já foi finalizado (`ENRIQUECIDO_APTO`, `INELEGIVEL_CPF`, `EXPIRADO`, `ENRIQUECIMENTO_FALHOU_CHAVE_OK`).
   
2. **Passo 2 — Triagem de Prazo Legal (Deadline First):**
   * Extrai o ano e mês da chave (`AAMM`). Pela lei da Nota Fiscal Paulista, um cupom só pode ser doado até o **dia 20 do segundo mês subsequente**.
   * **Descarte Seguro de Expirados:** Cupons de competências ultrapassadas (ex: Agosto/2026, vencido em 20/10/2026) são imediatamente atualizados no banco como `status_externo = "EXPIRADO"`, **sem gastar consultas à SEFAZ**.
   * **Priorização dos Vivos:** Os cupons vivos são enfileirados colocando a competência mais crítica primeiro: **Setembro/2026** (vence em 20/11) antes de **Outubro/2026** (vence em 20/12) e **Novembro/2026** (vence em 20/01/2027).

3. **Passo 3 — Validação Matemática Imediata (Módulo 11):**
   * Aplica o algoritmo oficial de pesos 2 a 9 da SEFAZ no 44º dígito.
   * Se o DV estiver matematicamente correto, o cupom é classificado como seguro. Caso a SEFAZ pública oscile ou demore, a nota é preservada com `ENRIQUECIMENTO_FALHOU_CHAVE_OK` para não ser descartada indevidamente da esteira de digitação (Motor 2).

4. **Passo 4 — Consulta Pública SEFAZ com Safe Crawling:**
   * Executa a requisição HTTP nativa contra o portal da Fazenda SP simulando navegador desktop.
   * Aplica atraso humano aleatório (1.5s a 4.0s) entre cupons para manter o IP da esteira 100% limpo e indetectável pelo WAF/F5.
   * Extrai:
     - Valor total do cupom (ex: `60.64`);
     - Data oficial de emissão (ex: `2026-10-30`);
     - Situação do consumidor: identifica se há CPF gravado no cupom. Se houver, a nota é classificada como `INELEGIVEL_CPF`. Se não houver (*"Consumidor não identificado"*), torna-se `ENRIQUECIDO_APTO`.

5. **Passo 5 — Persistência Isolada via PATCH:**
   * O sistema efetua `PATCH /cupons/{id}` enviando apenas:
     ```json
     {
       "status_externo": "ENRIQUECIDO_APTO",
       "detalhe_externo": null,
       "data_processamento_externo": "2026-11-13T18:30:00.000Z",
       "valor": 60.64,
       "data_emissao": "2026-10-30"
     }
     ```
   * Em caso de inegibilidade ou erro:
     ```json
     {
       "status_externo": "INELEGIVEL_CPF",
       "detalhe_externo": "Consumidor cadastrou CPF no caixa",
       "data_processamento_externo": "2026-11-13T18:30:00.000Z"
     }
     ```

---

## 3. Fluxo Operacional da Solução

```text
  [ Urnas / Leitores de QR ]
              │
              ▼
   [ API Gestão NFP ] ─── (GET /cupons?status=processamento_urna)
              │
              ▼
   [ Projeto Felix: Web App & Painel de Gatilhos ]
              │
              ├── 1. Leitura & Triagem Imediata de Chave (Módulo 11 + Prioridade Deadline First)
              │
              ├── 2. Consulta Pública SEFAZ SP (Módulo HTTPS nativo anti-bloqueio)
              │       ├─ Extração de Valor Total (R$) e Data de Emissão
              │       ├─ Extração de CNPJ do Emitente
              │       └─ Checagem de Consumidor (COM CPF vs SEM CPF)
              │
              ├── 3. Tratamento de Rejeições e Inelegibilidades
              │
              └── 4. Retorno Isolado (PATCH /cupons - status_externo, detalhe_externo, data_processamento_externo)
```

---

## 3. Telas e Funcionalidades

### 📊 Dashboard Executivo de Faturamento (`/`)
- **4 Cards Oficiais de Cobrança (Motor 1):**
  1. `TOTAL ENRIQUECIDO (FATURÁVEL)`: Soma exata dos cupons trabalhados (Aptos + Com Problema + Falhas com Chave OK).
  2. `VALIDADO E ENRIQUECIDO`: Cupons aptos sem CPF e enriquecidos com sucesso.
  3. `TOTAL COM PROBLEMA`: Cupons inelegíveis (com CPF de cliente no caixa ou expirados).
  4. `FALHA SEFAZ (ELEGÍVEL)`: Chave e DV autênticos, prontos para encaminhamento ao Motor 2 (Digitação).
- **Fechamento Dinâmico por Competência (Mês a Mês):**
  - Mapeia o volume real completo da base do parceiro (com paginação recursiva).
  - Tabela com colunas: Competência, Prazo Legal SEFAZ (com alertas de vencimento), Total na Base, Aptos, Com Problema, Falhas Elegíveis, Total Faturável, Restantes e % de Atingimento.
  - Filtro interativo para isolar qualquer mês com um clique.
- **Controle 2 (Motor de Digitação / SEFAZ):** Acompanhamento de Concluídos SEFAZ, Enviados, Confirmados em Relatório e Rejeitados pelo Portal.

### 🕹️ Painel de Gatilhos & Console de Operação (`/gatilhos`)
- **Autenticação Segura:** Token da API Gestão NFP configurado via `.env.local` e `localStorage`.
- **Gatilhos Operacionais:**
  - `Buscar Cupons Pendentes`: Varredura inteligente com filtro de exclusão e ordenação por prioridade legal de vencimento.
  - `Loop Contínuo (30s)`: Ciclo autônomo com temporizador e Heartbeat de segurança.
  - `Enriquecimento em Lote Seguro`: Jitter anti-bloqueio (1.5s a 4.0s) e parada de emergência.
- **Tabela Operacional com Comparativo Antes x Depois:**
  - Exibição de valores `null` vs valores enriquecidos, data de emissão, status de CPF e link direto para a consulta oficial da Fazenda SP.
- **Terminal de Logs em Tempo Real:** Classificação clara de eventos `[INFO]`, `[SUCCESS]`, `[WARN]` e `[ERROR]`.

---

## 4. Stack Tecnológica

| Camada | Tecnologia |
| :--- | :--- |
| **Framework** | [Next.js 15](https://nextjs.org/) (App Router, Serverless Functions) |
| **Linguagem** | [TypeScript](https://www.typescriptlang.org/) |
| **Estilização** | [Tailwind CSS](https://tailwindcss.com/) com paleta Slate/Dark |
| **Ícones** | [Lucide React](https://lucide.dev/) |
| **Cliente SEFAZ** | Node.js `https` nativo (bypass de bloqueios padrão do WAF/F5) |
| **Hospedagem** | [Vercel](https://vercel.com/) |

---

## 5. Como Executar Localmente

### Pré-requisitos
- Node.js 18+ (testado no Node.js v22)
- npm ou pnpm

### Passos:
1. Acesse o diretório do projeto:
   ```bash
   cd C:\apps\projetoFelix
   ```

2. Instale as dependências:
   ```bash
   npm install
   ```

3. Configure o arquivo `.env.local` na raiz:
   ```env
   NFP_API_TOKEN=nfpp_seu_token_aqui...
   ```

4. Inicie o servidor de desenvolvimento:
   ```bash
   npm run dev
   ```

5. Acesse no navegador:
   - **Dashboard:** [http://localhost:3000](http://localhost:3000)
   - **Gatilhos & Console:** [http://localhost:3000/gatilhos](http://localhost:3000/gatilhos)

---

## 6. Publicação na Vercel

O projeto foi construído especificamente para **deploy com zero configuração** na Vercel:

1. Suba o projeto para o GitHub / GitLab / Bitbucket.
2. Na Vercel, importe o repositório (`New Project`).
3. Em **Environment Variables**, adicione:
   - **Nome:** `NFP_API_TOKEN`
   - **Valor:** `nfpp_xxxxxxxxxxxxxxxxxxxxxxxx...`
4. Clique em **Deploy**. As rotas serverless `/api/triggers`, `/api/enrich` e `/api/dashboard/kpis` funcionarão imediatamente.
