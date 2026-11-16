# Plano de Execução e Processamento: App NFP (Projeto Felix)

Este repositório foi criado a partir das regras e códigos funcionais existentes em `C:\Users\murilo\Downloads\Projetos Python\bot`.

---

## 1. Mapeamento dos Arquivos-Fonte Originais

| Componente | Caminho do Arquivo Original | Trecho / Função Chave | O que aproveitar |
| :--- | :--- | :--- | :--- |
| **Consulta SEFAZ (Sem Captcha)** | `bot/IA_leitor_imagem_nfp.py` | `consultar_nfce_fazenda_sp(qr_data)` (linhas 93–371) | Requisição direta via URL pública `ConsultaQRCode.aspx?p=...`, headers simulados de browser e parser BeautifulSoup com fallback de regex para Valor, Data, CNPJ e Status. |
| **Validação da Chave** | `bot/IA_leitor_imagem_nfp.py` | `calcular_dv_chave(chave)` e `parse_chave_65` / `parse_chave_59` | Algoritmo de validação do dígito verificador módulo 11 e separador dos 44 dígitos (UF, ano, mês, CNPJ, modelo, série, número, etc.). |
| **Conexão com Banco de Dados** | `bot/importador_nfp_zeta.py` | Linhas 14–22 (`create_engine`, `mssql+pyodbc`) | String de conexão DSN/SQL Server `NFPSql`, credenciais e estrutura de pooling SQLAlchemy. |
| **Lógica de Digitação no Portal** | `bot/bot nfp/importacaoPyautogui.ipynb` | Células In[2], In[14] | Fluxo de telas do portal da Nota Fiscal Paulista (`https://www.nfp.fazenda.sp.gov.br/login.aspx`), campos de digitação, regras de retry e captura de retorno. |
| **Sessão Persistente / Autenticação** | `bot/consulta_nfp/obter_dados.py` | Linhas com `Selenium / ChromeOptions` e `user-data-dir` | Reutilização de perfil salvo do Chrome (`chrome_profile`) para evitar ter que refazer login e 2FA/Gov.br a cada execução. |

---

## 2. Arquitetura do Projeto Felix

```text
C:\apps\projetoFelix\
├── config\
│   └── settings.py          # Configurações de banco (DSN/ODBC), URLs e timeouts
├── core\
│   ├── db.py                # Conexão SQLAlchemy, busca cupons pendentes e update dos enriquecidos
│   ├── validator.py         # Cálculo de DV módulo 11 e normalização de chaves
│   ├── enricher.py          # Motor de consulta SEFAZ SP sem captcha (BeautifulSoup + Regex)
│   └── bot_digitador.py     # Automação de digitação web (Selenium/Playwright com perfil persistente)
├── logs\                    # Logs de execução diários
├── pipeline.py              # Orquestrador: [Enriquecimento] -> [Atualização DB] -> [Digitação Portal]
├── requirements.txt         # Dependências do projeto
└── PLANO_DE_EXECUCAO.md     # Este guia
```

---

## 3. Fluxo de Processamento

### **Etapa 1: Enriquecimento via SEFAZ (Sem Captcha)**
1. **Consulta no Banco:** Busca registros pendentes de enriquecimento com dados de QR Code preenchidos.
2. **Normalização do Payload:**
   - Se for URL completa: extrai o parâmetro `?p=`.
   - Se for apenas a chave (44 dígitos): formata `{chave}|1|1|1|1`.
3. **Requisição HTTP Direta:** Consulta `https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p={parametro_p}`.
4. **Extração de Dados:** Extrai Valor, Data de Emissão, CNPJ Emitente e Status.
5. **Persistência de Retorno:** Grava no banco e atualiza status para `ENRIQUECIDO`.

### **Etapa 2: Digitação Automática no Portal NFP**
1. **Sessão Persistente:** Inicia o navegador usando perfil persistente (`user-data-dir`) mantendo o login ativo.
2. **Entrada na Tela de Doação:** Direciona para a página de doação de cupons fiscais.
3. **Preenchimento e Envio:** Lança chave/dados enriquecidos e envia a nota.
4. **Captura do Resultado:** Registra retorno da SEFAZ (*Sucesso*, *Já Cadastrada*, *Expirada*) e atualiza o banco de dados.

---

## 4. Próximos Passos na Nova Conversa
1. Definir os nomes exatos da tabela e das colunas no banco SQL Server.
2. Configurar o perfil do navegador para a automação da digitação no portal da NFP.

