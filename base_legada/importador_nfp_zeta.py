#!/usr/bin/env python
# coding: utf-8

# --- Atualizado muma 15-12-2025 ---
import os
import json
import shutil
from collections import Counter
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

# --- Conexão com banco local (SQL Server via DSN) ---
dsn_local = 'NFPSql'
usuario_local = 'sa'
senha_local = ''

engine_local = create_engine(
    f'mssql+pyodbc://{usuario_local}:{senha_local}@{dsn_local}?driver=ODBC+Driver+17+for+SQL+Server'
)

# --- Caminhos ---
PASTA = r"G:\Drives compartilhados\NFP\zeta\output_scan_nfs"
PASTA_FEITO = os.path.join(PASTA, "feito")
PASTA_LOGS = os.path.join(PASTA, "logs")

os.makedirs(PASTA_FEITO, exist_ok=True)
os.makedirs(PASTA_LOGS, exist_ok=True)

# ------------- Helpers -------------
def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def to_int(x):
    try:
        s = safe_str(x)
        if s == "":
            return None
        s2 = s.replace(".", "").replace(",", "")
        return int(s2)
    except Exception:
        return None

def to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "":
        return None

    s = s.replace(" ", "").replace("R$", "")

    if s.count(",") == 1 and (s.count(".") > 1 or "." not in s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")

    try:
        return float(s)
    except:
        return None

def to_datetime(x):
    dt = pd.to_datetime(x, errors='coerce')
    if pd.isna(dt):
        return None
    return dt.to_pydatetime()

def formatar_cnpj(cnpj):
    c = ''.join(filter(str.isdigit, str(cnpj)))
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"

def make_json_serializable(obj):
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    try:
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
    except Exception:
        pass
    if isinstance(obj, (int, float, str, bool)):
        return obj
    try:
        return obj.item()
    except Exception:
        return str(obj)

def serialize_row_dict(row_dict):
    return {k: make_json_serializable(v) for k, v in row_dict.items()}

# ------------- Processamento de Excel -------------
def processar_excel(filepath):
    df = pd.read_excel(filepath, dtype=str).fillna("")
    validos, invalidos = [], []

    for _, row in df.iterrows():
        id_cupom = safe_str(row.get("id_cupom"))
        valor_nota = safe_str(row.get("valor_nota"))
        lote_cupom = to_int(row.get("lote"))

        if id_cupom and valor_nota and lote_cupom:
            registro = {
                "IdCupom": id_cupom,
                "Lote": lote_cupom,
                "DataCad": datetime.now(),  # agora
                "Chave": safe_str(row.get("codigo_nota")),
                "ValorNF": to_float(row.get("valor_nota")),
                "Ano": to_int(row.get("ano")),
                "Mes": to_int(row.get("mes")),
                "CNPJ": formatar_cnpj(row.get("cnpj")),
                "DataNF": to_datetime(row.get("data_emissao")),
                "NUmNF": to_int(row.get("numero")),
                "Sat": str(to_int(row.get("sat")) or " "),
                "UserCaptura": safe_str(row.get("usuario")),
                "DtCaptura": to_datetime(row.get("data_captura")),
                "tipo": "murilo_zeta"
            }
            validos.append(registro)
        else:
            invalidos.append({**row.to_dict(), "motivo": "Campos obrigatórios faltando"})
    return validos, invalidos

# ------------- Inserção no Banco com progresso + validação de CNPJ -------------
def inserir_no_banco(validos):
    erros_insercao = []
    rejeitados = []
    duplicidades = []
    with engine_local.begin() as conn:
        for idx, reg in enumerate(validos, start=1):
            # Validação CNPJ
            try:
                consulta = text("""
                    SELECT lit.CNPJ
                    FROM Lotes_Itens lit
                    WHERE lit.IdLote = :lote
                """)
                result = conn.execute(consulta, {"lote": reg["Lote"]}).fetchone()
                if result:
                    cnpj_lote_db = formatar_cnpj(result[0])
                    if cnpj_lote_db != reg["CNPJ"]:
                        rejeitados.append({**reg, "motivo": "CNPJ divergente", "cnpj_lote_db": cnpj_lote_db})
                        print(f"   ⚠️ Rejeitado (CNPJ divergente) IdCupom={reg['IdCupom']} lote={reg['Lote']}")
                        continue
                else:
                    rejeitados.append({**reg, "motivo": "Lote não encontrado"})
                    print(f"   ⚠️ Rejeitado (lote não encontrado) IdCupom={reg['IdCupom']} lote={reg['Lote']}")
                    continue
            except Exception as e:
                rejeitados.append({**reg, "motivo": f"Erro ao validar CNPJ do lote: {e}"})
                print(f"   ⚠️ Erro validação CNPJ IdCupom={reg['IdCupom']}: {e}")
                continue

            # tentativa de inserção
            comando = text("""
                INSERT INTO LotesIntegracao 
                (IdCupom, Lote, DataCad, Chave, ValorNF, Ano, Mes, CNPJ, DataNF, NUmNF, Sat, UserCaptura, DtCaptura, tipo)
                VALUES (:IdCupom, :Lote, :DataCad, :Chave, :ValorNF, :Ano, :Mes, :CNPJ, :DataNF, :NUmNF, :Sat, :UserCaptura, :DtCaptura, :tipo)
            """)
            try:
                conn.execute(comando, reg)
            except Exception as e:
                erro_str = str(e).lower()
                if "duplicate" in erro_str or "primary key" in erro_str or "unique" in erro_str:
                    duplicidades.append({"IdCupom": reg["IdCupom"], "erro": "duplicidade"})
                else:
                    erros_insercao.append({"IdCupom": reg["IdCupom"], "erro": str(e)})

            if idx % 10 == 0 or idx == len(validos):
                print(f"   ➡️ Processados {idx}/{len(validos)} (válidos originais)")

    return erros_insercao, rejeitados, duplicidades

# ------------- Main -------------
def main():
    for arquivo in os.listdir(PASTA):
        if not arquivo.endswith(".xlsx") or arquivo.startswith("~$"):
            continue

        filepath = os.path.join(PASTA, arquivo)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(arquivo)[0]
        pasta_saida = os.path.join(PASTA_LOGS, f"{base_name}_{timestamp}")
        os.makedirs(pasta_saida, exist_ok=True)

        log_file = os.path.join(pasta_saida, f"import_log_{base_name}_{timestamp}.txt")
        json_rejeitados = os.path.join(pasta_saida, f"rejeitados_{base_name}_{timestamp}.json")
        erros_insercao_csv = os.path.join(pasta_saida, f"erros_insercao_{base_name}_{timestamp}.csv")
        duplicidades_csv = os.path.join(pasta_saida, f"duplicidades_{base_name}_{timestamp}.csv")

        rejeitados_total = []
        erros_insercao_total = []
        duplicidades_total = []

        print(f"\n📂 Processando arquivo: {arquivo}")
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"=== LOG IMPORTAÇÃO ZETA {datetime.now()} ===\n\n")

            try:
                validos, invalidos = processar_excel(filepath)
                print(f"   ✅ {len(validos)} registros válidos | ❌ {len(invalidos)} inválidos")
                log.write(f"Encontrados - válidos: {len(validos)}, inválidos: {len(invalidos)}\n")

                rejeitados_total.extend(invalidos)

                if validos:
                    print("   🔄 Inserindo registros no banco...")
                    erros_insercao, rejeitados_cnpj, duplicidades = inserir_no_banco(validos)
                    erros_insercao_total.extend(erros_insercao)
                    rejeitados_total.extend(rejeitados_cnpj)
                    duplicidades_total.extend(duplicidades)

                    if erros_insercao:
                        print(f"   ⚠️ {len(erros_insercao)} outros erros de inserção")
                    if rejeitados_cnpj:
                        print(f"   ⚠️ {len(rejeitados_cnpj)} rejeitados por CNPJ/lote")
                    if duplicidades:
                        print(f"   ⚠️ {len(duplicidades)} duplicidades detectadas")

                    inserted_count = max(0, len(validos) - len(rejeitados_cnpj) - len(erros_insercao) - len(duplicidades))
                else:
                    inserted_count = 0

                log.write(f"Importados (estimado): {inserted_count}\n")
                log.write(f"Rejeitados totais: {len(rejeitados_total)}\n")
                log.write(f"Duplicidades: {len(duplicidades_total)}\n\n")

                if rejeitados_total:
                    rejeitados_serial = [serialize_row_dict(r) for r in rejeitados_total]
                    with open(json_rejeitados, "w", encoding="utf-8") as f:
                        json.dump(rejeitados_serial, f, ensure_ascii=False, indent=2)
                    print(f"❌ JSON de registros rejeitados salvo em {json_rejeitados}")

                    motivos = [r.get("motivo", "sem_motivo") for r in rejeitados_total]
                    cnt = Counter(motivos)
                    log.write("Rejeitados por motivo:\n")
                    for motivo, q in cnt.items():
                        log.write(f"  - {motivo}: {q}\n")

                if erros_insercao_total:
                    pd.DataFrame(erros_insercao_total).to_csv(erros_insercao_csv, index=False, sep=";")
                    print(f"❌ {len(erros_insercao_total)} erros de inserção salvos em {erros_insercao_csv}")

                if duplicidades_total:
                    pd.DataFrame(duplicidades_total).to_csv(duplicidades_csv, index=False, sep=";")
                    print(f"⚠️ {len(duplicidades_total)} duplicidades salvas em {duplicidades_csv}")

                destino = os.path.join(PASTA_FEITO, arquivo)
                shutil.move(filepath, destino)
                print(f"📦 Arquivo movido para {destino}")
                log.write(f"Arquivo movido para: {destino}\n")

            except Exception as e:
                print(f"⚠️ Erro no arquivo {arquivo}: {e}")
                log.write(f"Erro no arquivo {arquivo}: {e}\n\n")

    print("\n✅ Processo concluído! Veja detalhes nos logs.")

if __name__ == "__main__":
    main()