#!/usr/bin/env python
# coding: utf-8
# IA_leitor_imagem_nfp_v2.py
# Versão 2025-10-28 - Detecta QR, extrai chave (modelos 65 e 59), fallback por OCR e gera XLSX.
# teste muma

import os
import re
import warnings
import subprocess
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import pandas as pd
import numpy as np
import requests
from urllib.parse import quote
import time
import json

# Suprime warnings da biblioteca zbar/pyzbar
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', message='.*zbar.*')
warnings.filterwarnings('ignore', message='.*pdf417.*')
from bs4 import BeautifulSoup

# QR / imagem
import cv2
from pyzbar.pyzbar import decode as zbar_decode

# === CONFIG BÁSICA (ajuste se necessário) ===
BASE_PATH = r"C:\Users\murilo\Downloads\Projetos Python\bot\notas"
OUTPUT_FILENAME = "consolidado_notas_{ts}.xlsx"

# 🎛️ CONTROLE DE DEBUG - Mude aqui para habilitar/desabilitar debug
DEBUG_HABILITADO = True  # True = mostra debug detalhado | False = produção silenciosa
# Configuração do Tesseract - usa o PATH se disponível
try:
    # Tenta usar tesseract do PATH primeiro
    subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
    # Se chegou aqui, tesseract está no PATH
except:
    # Fallback para caminho específico
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\murilo\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Mantive as variáveis de banco local que você pediu pra guardar (usaremos depois)
dsn_local = os.getenv("ZETA_DSN", "NFPSql")
usuario_local = os.getenv("ZETA_DB_USER", "sa")
senha_local = os.getenv("ZETA_DB_PASS", "")

# Regex utilitárias
RE_ONLY_DIGITS = re.compile(r"\D+")
RE_44 = re.compile(r"\b(\d{44})\b")

def calcular_dv_chave(chave):
    """
    Calcula o dígito verificador de uma chave de 44 dígitos conforme CF-e-SAT
    Baseado na função VB.NET fornecida pelo usuário
    """
    if not chave or len(chave) != 44:
        return None
    
    if not chave.isdigit():
        return None
    
    # Pesos conforme a regra do CF-e-SAT
    pesos = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2,
             9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7,
             6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4,
             3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    soma = 0
    
    # Aplica ponderação nos primeiros 43 dígitos
    for i in range(43):
        digito = int(chave[i])
        peso = pesos[i]
        soma += digito * peso
    
    # Calcula resto da divisão por 11
    resto = soma % 11
    
    # Define DV conforme regra
    dv_calculado = 11 - resto
    if dv_calculado >= 10:
        dv_calculado = 0
    
    # DV atual da chave (44º dígito)
    dv_informado = int(chave[43])
    
    return dv_calculado == dv_informado

def consultar_nfce_fazenda_sp(qr_data, debug=False):
    """
    Consulta NFCe no site da Fazenda SP para validar dados
    Aceita: QR completo, URL completa, ou apenas chave de 44 dígitos
    """
    try:
        if not qr_data:
            return None
        
        # Se o QR já é uma URL completa, extrai apenas o parâmetro p=
        if "?p=" in qr_data:
            parametro_p = qr_data.split("?p=")[1]
        else:
            # Verifica se é apenas uma chave de 44 dígitos (só números)
            chave_limpa = ''.join(filter(str.isdigit, qr_data))
            if len(chave_limpa) == 44 and chave_limpa.isdigit():
                # Monta parâmetro no formato aceito pelo site: CHAVE|1|1|1|1
                parametro_p = f"{chave_limpa}|1|1|1|1"
            else:
                # QR contém os dados já formatados
                parametro_p = qr_data
        
        # URL base da consulta
        base_url = "https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx"
        url_completa = f"{base_url}?p={quote(parametro_p)}"
        
        # DEBUG: Mostra URL completa de acesso
        if DEBUG_HABILITADO:
            print(f"🌐 URL de consulta: {url_completa}")
        
        # Headers para simular navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Faz a requisição
        response = requests.get(url_completa, headers=headers, timeout=10)
        
        # DEBUG: Mostra status da resposta
        if DEBUG_HABILITADO:
            print(f"🌐 Status HTTP: {response.status_code}")
        
        if response.status_code != 200:
            return None
        
        # Parse do HTML
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            dados_extraidos = {}
            
            # === BUSCA VALOR ===
            valor_encontrado = False
            
            # Método 0: Busca por ID totalNota (MAIS PRIORITÁRIO)
            elemento_total = soup.find(id='totalNota')
            if elemento_total:
                texto_total = elemento_total.get_text()
                match = re.search(r'(\d+[,\.]\d{2})', texto_total)
                if match:
                    dados_extraidos['valor_site'] = match.group(1)
                    valor_encontrado = True
            
            # Método 0B: Busca por classe .valor
            if not valor_encontrado:
                elementos_valor = soup.find_all(class_="valor")
                for elem in elementos_valor:
                    texto = elem.get_text().strip()
                    match = re.search(r'^(\d+[,\.]\d{2})$', texto)
                    if match:
                        dados_extraidos['valor_site'] = match.group(1)
                        valor_encontrado = True
                        break
            
            # Método 0C: Busca por classe totalNumb
            if not valor_encontrado:
                elementos_total = soup.find_all(class_=re.compile(r'totalNumb'))
                for elem in elementos_total:
                    texto = elem.get_text().strip()
                    classes = elem.get('class', [])
                    if ('txtMax' in classes or re.match(r'^\d+[,\.]\d{2}$', texto)):
                        match = re.search(r'^(\d+[,\.]\d{2})$', texto)
                        if match:
                            dados_extraidos['valor_site'] = match.group(1)
                            valor_encontrado = True
                            break
            
            # Método 1: Busca por texto "Valor a pagar R$:"
            if not valor_encontrado:
                elementos_valor_pagar = soup.find_all(string=re.compile(r'Valor\s+a\s+pagar\s+R\$\s*:', re.I))
                for elem in elementos_valor_pagar:
                    parent = elem.parent
                    if parent:
                        texto_completo = parent.get_text()
                        match = re.search(r'Valor\s+a\s+pagar\s+R\$\s*:\s*(\d+[,\.]\d{2})', texto_completo, re.I)
                        if match:
                            dados_extraidos['valor_site'] = match.group(1)
                            valor_encontrado = True
                            break
                    
                    # Busca em elementos próximos
                    for sibling in parent.next_siblings:
                        if hasattr(sibling, 'get_text'):
                            texto_sibling = sibling.get_text()
                            match = re.search(r'R\$\s*(\d+[,\.]\d{2})', texto_sibling)
                            if match:
                                dados_extraidos['valor_site'] = match.group(1)
                                valor_encontrado = True
                                break
            
            # Método 1B: Busca mais ampla por "Valor a pagar"
            if not valor_encontrado:
                elementos_pagar = soup.find_all(string=re.compile(r'Valor\s+a\s+pagar', re.I))
                for elem in elementos_pagar:
                    # Busca valor em toda a área ao redor
                    contexto = elem.parent.parent if elem.parent and elem.parent.parent else elem.parent
                    if contexto:
                        texto_contexto = contexto.get_text()
                        match = re.search(r'R\$\s*(\d+[,\.]\d{2})', texto_contexto)
                        if match:
                            dados_extraidos['valor_site'] = match.group(1)
                            valor_encontrado = True
                            break
            
            # Método 2: Busca por IDs que começam com "Item" + td[2] + span
            if not valor_encontrado:
                # Busca elementos com ID que começa com "Item"
                items = soup.find_all(id=re.compile(r'^Item\d*', re.I))
                for item in items:
                    # Busca td[2] (segunda coluna)
                    tds = item.find_all('td')
                    if len(tds) >= 2:  # Tem pelo menos 2 colunas
                        segunda_coluna = tds[1]  # td[2] é índice 1
                        # Busca span dentro da segunda coluna
                        spans = segunda_coluna.find_all('span')
                        for span in spans:
                            texto = span.get_text().strip()
                            match = re.search(r'R\$\s*(\d+[,\.]\d{2})', texto)
                            if match:
                                dados_extraidos['valor_site'] = match.group(1)
                                valor_encontrado = True
                                break
                    if valor_encontrado:
                        break
            
            # Método 3: Busca o maior valor monetário, mas filtra tributos
            if not valor_encontrado:
                valores_encontrados = []
                todos_textos = soup.get_text()
                matches = re.findall(r'R\$\s*(\d+[,\.]\d{2})', todos_textos)
                
                for match in matches:
                    try:
                        # Converte para float para comparação
                        valor_str = match.replace(',', '.')
                        valor_num = float(valor_str)
                        
                        # FILTRO MAIS RESTRITIVO: valores >= R$ 10,00 
                        # (evita tributos pequenos como R$ 5,35)
                        if valor_num >= 10.0:
                            valores_encontrados.append((valor_num, match))
                    except:
                        continue
                
                if valores_encontrados:
                    # Pega o valor mais provável (primeiro da lista de valores altos)
                    valor_escolhido = valores_encontrados[0]  # Primeiro valor >= R$ 10
                    dados_extraidos['valor_site'] = valor_escolhido[1]
                    valor_encontrado = True
                    
                # Se não achou nada >= R$ 10, usa critério mais flexível
                elif not valor_encontrado:
                    valores_backup = []
                    for match in matches:
                        try:
                            valor_str = match.replace(',', '.')
                            valor_num = float(valor_str)
                            if valor_num >= 5.0:  # Backup: >= R$ 5
                                valores_backup.append((valor_num, match))
                        except:
                            continue
                    
                    if valores_backup:
                        maior_backup = max(valores_backup, key=lambda x: x[0])
                        dados_extraidos['valor_site'] = maior_backup[1]
                        valor_encontrado = True
            
            # Método 4: Busca em tabelas com estrutura específica
            if not valor_encontrado:
                # Busca tabelas e suas linhas finais (onde geralmente fica o total)
                tabelas = soup.find_all('table')
                for tabela in tabelas:
                    rows = tabela.find_all('tr')
                    # Verifica as últimas 3 linhas da tabela (onde ficam os totais)
                    for row in rows[-3:]:
                        texto_linha = row.get_text()
                        # Procura por palavras-chave de total
                        if any(palavra in texto_linha.lower() for palavra in ['total', 'pagar', 'valor']):
                            match = re.search(r'R\$\s*(\d+[,\.]\d{2})', texto_linha)
                            if match:
                                dados_extraidos['valor_site'] = match.group(1)
                                valor_encontrado = True
                                break
                    if valor_encontrado:
                        break
            
            # Fallback: Se nada funcionou, busca qualquer valor com cuidado
            if not valor_encontrado:
                valor_elementos = soup.find_all(string=re.compile(r'R\$\s*\d+[,\.]\d{2}'))
                for elem in valor_elementos:
                    elem_str = str(elem).strip()
                    # Evita JavaScript, tributos e textos técnicos
                    if ('function' not in elem_str and '$(document)' not in elem_str and 
                        'setTimeout' not in elem_str and 'tribut' not in elem_str.lower() and
                        'aproxim' not in elem_str.lower() and len(elem_str) < 100):
                        match = re.search(r'R\$\s*(\d+[,\.]\d{2})', elem_str)
                        if match:
                            dados_extraidos['valor_site'] = match.group(1)
                            valor_encontrado = True
                            break
                    "div[class*='total'] span",
                    "div[class*='valor'] span",
                    "span[class*='total']",
            
            # Log do resultado da extração de valor
            if not valor_encontrado:
                pass
            
            # === BUSCA DATA ===
            data_elementos = soup.find_all(string=re.compile(r'\d{2}/\d{2}/\d{4}'))
            for elem in data_elementos:
                match = re.search(r'(\d{2}/\d{2}/\d{4})', str(elem))
                if match:
                    dados_extraidos['data_site'] = match.group(1)
                    break
            
            # === BUSCA STATUS ===
            status_elementos = soup.find_all(string=re.compile(r'Autorizada|Cancelada|Denegada|Rejeitada|Inutilizada'))
            for elem in status_elementos:
                elem_str = str(elem).strip()
                # Evita JavaScript
                if ('function' not in elem_str and '$(document)' not in elem_str and 
                    'setTimeout' not in elem_str and len(elem_str) < 50):
                    dados_extraidos['status_site'] = elem_str
                    break
            
            # === BUSCA CNPJ ===
            cnpj_elementos = soup.find_all(string=re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'))
            for elem in cnpj_elementos:
                match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', str(elem))
                if match:
                    dados_extraidos['cnpj_site'] = match.group(1)
                    break
            
            return dados_extraidos
            
        except Exception as e:
            # Fallback: regex simples
            dados_extraidos = {}
            
            valor_match = re.search(r'R\$\s*(\d+[,\.]\d{2})', response.text)
            if valor_match:
                dados_extraidos['valor_site'] = valor_match.group(1)
            
            data_match = re.search(r'(\d{2}/\d{2}/\d{4})', response.text)
            if data_match:
                dados_extraidos['data_site'] = data_match.group(1)
            
            return dados_extraidos
        
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None

def validar_chave_completa(chave, qr_data=None):
    """
    Validação completa da chave fiscal
    """
    if not chave:
        return False, {}
    
    # Remove espaços e caracteres especiais
    chave_limpa = re.sub(r'\D', '', chave)
    
    if len(chave_limpa) != 44:
        return False, {}
    
    # 1. Validar DV
    dv_valido = calcular_dv_chave(chave_limpa)
    if not dv_valido:
        return False, {'dv_valido': False}
    
    resultado = {'dv_valido': True, 'chave_validada': chave_limpa}
    
    # 2. Consulta online (se QR disponível)
    if qr_data:
        dados_site = consultar_nfce_fazenda_sp(qr_data)
        if dados_site:
            resultado.update(dados_site)
            resultado['consulta_online'] = True
        else:
            resultado['consulta_online'] = False
    
    return True, resultado
RE_3525_PLUS = re.compile(r"3525(\d{44})")
# Nova regex para chave com espaços ou formatação
RE_CHAVE_ESPACADA = re.compile(r"3525[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})")
# Regex para chave começando com 3525 (mais flexível)
RE_CHAVE_3525_FLEX = re.compile(r"3525[\s\-]*[\d\s\-]{39,60}")
RE_CNPJ = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b")
RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
RE_VALOR = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")
# Nova regex para valor na linha do Total
RE_VALOR_TOTAL = re.compile(r"Total[\s\w$]*R\$[\s]*(\d{1,3}(?:\.\d{3})*,\d{2})")
RE_SAT = re.compile(r"(?i)\bSAT[:\s\-]*?(\d{1,12})\b")
RE_NUM_CUPOM = re.compile(r"(?i)\b(?:COO|CUPOM|Nº|N[°o])[:\s\-]*?(\d{1,12})\b")

# --- funções utilitárias ---
def somente_digitos(s):
    if not s:
        return ""
    return RE_ONLY_DIGITS.sub("", str(s))

def formatar_cnpj(cnpj):
    c = somente_digitos(cnpj)
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"

def parse_chave_65(chave):
    """Parse da chave (modelo 65) seguindo sua descrição."""
    # indexes 1-based em sua descrição -> converter para 0-based slices
    # 1-2 UF => [0:2]
    # 3-4 ano => [2:4]
    # 5-6 mes => [4:6]
    # 7-20 cnpj => [6:20]
    # 21-22 modelo => [20:22]
    # 23-25 serie => [22:25]
    # 26-34 numero => [25:34]
    # 35-43 codigo numerico => [34:43]
    # 44 dv => [43]
    if len(chave) != 44:
        return {}
    return {
        "uf": chave[0:2],
        "ano_2": chave[2:4],
        "mes": chave[4:6],
        "cnpj": formatar_cnpj(chave[6:20]),
        "modelo": chave[20:22],
        "serie": chave[22:25],
        "numero": chave[25:34].lstrip("0"),
        "codigo_num": chave[34:43],
        "dv": chave[43]
    }

def parse_chave_59(chave):
    """Parse da chave (modelo 59) seguindo a composição correta:
       1-2 UF
       3-4 Ano
       5-6 Mês
       7-20 CNPJ emitente
       21-22 Modelo
       23-31 SAT
       32-40 Número do cupom
       41-43 Código numérico
       44 Dígito verificador
    """
    if len(chave) != 44:
        return {}
    return {
        "uf": chave[0:2],
        "ano_2": chave[2:4],
        "mes": chave[4:6],
        "cnpj": formatar_cnpj(chave[6:20]),
        "modelo": chave[20:22],
        "sat": chave[22:31].lstrip("0"),
        "numero": chave[31:37].lstrip("0"),
        "codigo_num": chave[37:43],
        "dv": chave[43]
    }


def inferir_modelo_e_parse(chave):
    """
    Decide se a chave deve ser interpretada como modelo 65 ou 59.
    A heurística: olhar os dígitos 20:22 (posição 21-22 human), se igual a '65' ou '59'
    """
    pass
    if not chave or len(chave) != 44:
        pass
        return {}
    modelo = chave[20:22]
    pass
    if modelo == "65":
        parsed = parse_chave_65(chave)
        parsed["parsed_from"] = "chave_65"
        pass
        return parsed
    elif modelo == "59":
        parsed = parse_chave_59(chave)
        parsed["parsed_from"] = "chave_59"
        pass
        return parsed
    else:
        pass
        # modelo desconhecido: tenta ambos (prefira 65 se sat vazio)
        p65 = parse_chave_65(chave)
        p59 = parse_chave_59(chave)
        # heurística simples: se p59 tem sat preenchido plausível (1-6 dígitos) e p65.msmes plausível
        if p59.get("sat"):
            p59["parsed_from"] = "chave_59_guess"
            pass
            return p59
        p65["parsed_from"] = "chave_65_guess"
        pass
        return p65

# --- OCR e QR ---
def verificar_tesseract():
    """Verifica se o Tesseract está funcionando corretamente"""
    try:
        pass
        # Testa com uma imagem simples em memória
        from PIL import Image
        
        # Cria uma imagem de teste simples
        img_test = Image.new('RGB', (100, 30), color='white')
        
        # Testa o OCR
        result = pytesseract.image_to_string(img_test, lang="por")
        pass
        
        # Verifica idiomas disponíveis
        langs = pytesseract.get_languages()
        pass
        
        if 'por' in langs:
            pass
        else:
            pass
            
        return True
        
    except Exception as e:
        pass
        return False


def melhorar_imagem_para_ocr(image_path):
    """
    Aplica várias técnicas de melhoria de imagem para OCR.
    Testa diferentes abordagens e retorna a melhor imagem processada.
    """
    
    try:
        # Carrega imagem original
        img_original = Image.open(image_path)
        img_cv = cv2.imread(image_path)
        
        # Lista de melhorias para testar
        melhorias = []
        
        # 1. Imagem original (baseline)
        melhorias.append(("original", img_original))
        
        # 2. Ajuste de brilho e contraste automático
        try:
            # Para imagens escuras - aumenta brilho
            enhancer_bright = ImageEnhance.Brightness(img_original)
            img_brilhante = enhancer_bright.enhance(1.3)  # 30% mais brilho
            
            enhancer_contrast = ImageEnhance.Contrast(img_brilhante)
            img_brilho_contraste = enhancer_contrast.enhance(1.2)  # 20% mais contraste
            
            melhorias.append(("brilho_contraste", img_brilho_contraste))
            pass
        except Exception as e:
            pass
        
        # 3. Para imagens muito escuras - correção gamma
        try:
            img_array = np.array(img_original)
            # Gamma correction (gamma < 1 clareia a imagem)
            gamma = 0.7
            img_gamma = np.power(img_array / 255.0, gamma) * 255.0
            img_gamma = np.uint8(img_gamma)
            img_gamma_pil = Image.fromarray(img_gamma)
            
            melhorias.append(("gamma_clareamento", img_gamma_pil))
            pass
        except Exception as e:
            pass
        
        # 4. Equalização de histograma (para imagens com baixo contraste)
        try:
            img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            img_eq = cv2.equalizeHist(img_gray)
            img_eq_pil = Image.fromarray(img_eq).convert('RGB')
            
            melhorias.append(("equalizacao", img_eq_pil))
            pass
        except Exception as e:
            pass
        
        # 5. CLAHE (Contrast Limited Adaptive Histogram Equalization)
        try:
            img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            img_clahe = clahe.apply(img_gray)
            img_clahe_pil = Image.fromarray(img_clahe).convert('RGB')
            
            melhorias.append(("clahe", img_clahe_pil))
            pass
        except Exception as e:
            pass
        
        # 6. Sharpen (para imagens borradas)
        try:
            img_sharp = img_original.filter(ImageFilter.SHARPEN)
            enhancer_sharp = ImageEnhance.Sharpness(img_sharp)
            img_mais_sharp = enhancer_sharp.enhance(1.5)
            
            melhorias.append(("sharpen", img_mais_sharp))
            pass
        except Exception as e:
            pass
        
        # 7. Combinação: brilho + contraste + sharpen
        try:
            enhancer_bright = ImageEnhance.Brightness(img_original)
            img_temp = enhancer_bright.enhance(1.2)
            
            enhancer_contrast = ImageEnhance.Contrast(img_temp)
            img_temp = enhancer_contrast.enhance(1.3)
            
            enhancer_sharp = ImageEnhance.Sharpness(img_temp)
            img_combinada = enhancer_sharp.enhance(1.3)
            
            melhorias.append(("combinada", img_combinada))
            pass
        except Exception as e:
            pass
        
        # 8. Morfologia (para melhorar texto)
        try:
            img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            # Threshold binário
            _, binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY)
            # Operações morfológicas
            kernel = np.ones((2,2), np.uint8)
            opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
            img_morfologia = Image.fromarray(closing).convert('RGB')
            
            melhorias.append(("morfologia", img_morfologia))
            pass
        except Exception as e:
            pass
        
        # 9. Para imagens muito claras - escurecer um pouco
        try:
            enhancer_bright = ImageEnhance.Brightness(img_original)
            img_escura = enhancer_bright.enhance(0.8)  # 20% menos brilho
            
            enhancer_contrast = ImageEnhance.Contrast(img_escura)
            img_escura_contraste = enhancer_contrast.enhance(1.4)  # 40% mais contraste
            
            melhorias.append(("escurecer_contraste", img_escura_contraste))
            pass
        except Exception as e:
            pass
        
        pass
        
        # Testa OCR em cada melhoria e escolhe a melhor
        melhor_imagem = img_original
        melhor_nome = "original"
        melhor_score = 0
        melhor_texto = ""
        
        for nome, img in melhorias:
            try:
                pass
                texto = pytesseract.image_to_string(img, lang="por")
                
                # Score baseado em: tamanho do texto + presença de dígitos + presença de palavras-chave
                score = len(texto)
                score += len(re.findall(r'\d', texto)) * 2  # dígitos valem mais
                score += texto.count('3525') * 100  # chave vale muito mais
                score += texto.upper().count('TOTAL') * 30  # total vale mais
                score += texto.upper().count('R$') * 15  # valor vale mais
                score += len(re.findall(r'\d{2}/\d{2}/\d{4}', texto)) * 25  # datas valem mais
                
                pass
                
                if score > melhor_score:
                    melhor_score = score
                    melhor_imagem = img
                    melhor_nome = nome
                    melhor_texto = texto
                    pass
                    
            except Exception as e:
                pass
        
        pass
        
        return melhor_imagem, melhor_nome, melhor_texto
        
    except Exception as e:
        pass
        # Retorna imagem original em caso de erro
        img_original = Image.open(image_path)
        texto_original = pytesseract.image_to_string(img_original, lang="por")
        return img_original, "original_erro", texto_original


def ocr_text_from_image(path):
    pass
    try:
        img_pil = Image.open(path)
        
        # Lista de métodos de pré-processamento COM NOVAS MELHORIAS
        metodos_processamento = []
        
        # 🆕 MELHORIA 1: Configurações OCR otimizadas baseadas no diagnóstico
        configs_ocr = [
            ("--psm 12", "Texto esparso OSD"),  # MELHOR do diagnóstico
            ("--psm 11", "Texto esparso"), 
            ("--psm 6", "Página única"),
            ("--psm 3", "Padrão")
        ]
        
        # 1. Original com múltiplas configurações OCR
        for config, nome_config in configs_ocr:
            try:
                texto_original = pytesseract.image_to_string(img_pil, lang="por", config=config)
                metodos_processamento.append((f"original_{nome_config}", texto_original))
            except:
                pass
        
        # 🆕 MELHORIA 2: Escala de cinza (MELHOR pré-processamento do diagnóstico)
        try:
            import cv2
            img_cv = cv2.imread(path)
            if img_cv is not None:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                img_gray_pil = Image.fromarray(gray)
                
                # Testa escala de cinza com as melhores configurações OCR
                for config, nome_config in configs_ocr[:2]:  # Só as 2 melhores
                    try:
                        texto_gray = pytesseract.image_to_string(img_gray_pil, lang="por", config=config)
                        metodos_processamento.append((f"gray_{nome_config}", texto_gray))
                    except:
                        pass
        except:
            pass
        
        # 2. OTSU (método já existente - mantido por compatibilidade)
        try:
            import cv2
            img_cv = cv2.imread(path)
            if img_cv is not None:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                # Teste OTSU com melhor configuração
                texto_otsu = pytesseract.image_to_string(otsu, lang="por", config="--psm 12")
                metodos_processamento.append(("otsu_psm12", texto_otsu))
        except:
            pass
        
        # 🆕 MELHORIA 3: Denoising (segunda melhor do diagnóstico)
        try:
            import cv2
            img_cv = cv2.imread(path)
            if img_cv is not None:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                denoised = cv2.fastNlMeansDenoising(gray)
                img_denoised_pil = Image.fromarray(denoised)
                texto_denoised = pytesseract.image_to_string(img_denoised_pil, lang="por", config="--psm 12")
                metodos_processamento.append(("denoised_psm12", texto_denoised))
        except:
            pass
        
        # 3. Contraste aumentado (método já existente - mantido)
        try:
            enhancer = ImageEnhance.Contrast(img_pil)
            enhanced = enhancer.enhance(2.0)
            texto_contrast = pytesseract.image_to_string(enhanced, lang="por")
            metodos_processamento.append(("contrast", texto_contrast))
        except:
            pass
        
        # 4. Denoising
        try:
            import cv2
            img_cv = cv2.imread(path)
            if img_cv is not None:
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                denoised = cv2.fastNlMeansDenoising(gray)
                _, thresh_denoised = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                texto_denoised = pytesseract.image_to_string(thresh_denoised, lang="por")
                metodos_processamento.append(("denoised", texto_denoised))
        except:
            pass
        
        # Seleciona o melhor texto baseado em critérios de qualidade MELHORADOS
        melhor_texto = ""
        melhor_score = 0
        melhor_metodo = ""
        
        for metodo, texto in metodos_processamento:
            if texto:
                # 🆕 SCORE MELHORADO baseado no diagnóstico
                score = 0
                
                # 1. Comprimento básico (mais texto geralmente é melhor)
                score += len(texto.strip()) * 0.1
                
                # 2. Dígitos (importantes para dados fiscais)
                digitos = len([c for c in texto if c.isdigit()])
                score += digitos * 0.5
                
                # 3. Palavras-chave fiscais (peso alto)
                score += texto.count("3525") * 100  # Chave fiscal
                score += texto.upper().count("TOTAL") * 15
                score += texto.count("R$") * 20
                score += texto.upper().count("VALOR") * 10
                score += texto.upper().count("CNPJ") * 25
                score += texto.upper().count("NOTA") * 5
                score += texto.upper().count("FISCAL") * 5
                
                # 4. Valores monetários válidos (NOVO - baseado no diagnóstico)
                import re
                valores_monetarios = re.findall(r'\d{1,3}(?:[.,]\d{2})', texto)  # Formato flexível
                score += len(valores_monetarios) * 20
                
                # 5. Datas válidas
                datas = re.findall(r'\d{2}/\d{2}/\d{4}', texto)
                score += len(datas) * 15
                
                # 6. CNPJ/CPF parciais
                cnpjs = re.findall(r'\d{2,3}[\s\.]?\d{3}[\s\.]?\d{3}', texto)
                score += len(cnpjs) * 10
                
                # 7. Bonus para métodos específicos que funcionaram bem no diagnóstico
                if "psm12" in metodo or "psm 12" in metodo:
                    score += 20  # Bonus para configuração que funcionou melhor
                if "gray" in metodo:
                    score += 15  # Bonus para escala de cinza
                if "denoised" in metodo:
                    score += 10  # Bonus para denoising
                
                pass
                
                if score > melhor_score:
                    melhor_score = score
                    melhor_texto = texto
                    melhor_metodo = metodo
                    pass
        
        # Fallback para inglês se português não funcionou
        if not melhor_texto:
            try:
                melhor_texto = pytesseract.image_to_string(img_pil, lang="eng")
                pass
            except:
                pass
        
        # Debug: mostra algumas linhas importantes
        if melhor_texto:
            linhas = melhor_texto.split('\n')
            pass
            for linha in linhas:
                if any(palavra in linha.upper() for palavra in ['TOTAL', 'VALOR', 'PAGAR', 'R$']):
                    pass
        
        return melhor_texto
    except Exception as e:
        pass
        return ""

def read_qr_from_image(path):
    """
    Tenta ler QR codes usando pyzbar com múltiplas configurações.
    Retorna lista de dados decodificados.
    """
    pass
    try:
        img = cv2.imread(path)
        if img is None:
            pass
            return []
        
        qr_data_found = []
        
        # Método 1: Imagem original em escala de cinza
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            decoded = zbar_decode(gray)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 2: Imagem com threshold binário
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            decoded = zbar_decode(binary)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 3: Threshold adaptativo
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            decoded = zbar_decode(adaptive)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 4: Melhoria de contraste
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            decoded = zbar_decode(enhanced)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 5: Redimensionamento (aumentar imagem)
        try:
            height, width = img.shape[:2]
            img_resized = cv2.resize(img, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            decoded = zbar_decode(gray)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 6: Blur + threshold (para imagens com ruído)
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            decoded = zbar_decode(binary)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 7: Múltiplos thresholds
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            for threshold_val in [80, 100, 120, 140, 160, 180, 200]:
                _, binary = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY)
                decoded = zbar_decode(binary)
                qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
                if qr_data:
                    qr_data_found.extend(qr_data)
                    pass
                    break  # Para no primeiro que funcionar
        except Exception as e:
            pass
        
        # Método 8: Morfologia (erosão + dilatação)
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            kernel = np.ones((2,2), np.uint8)
            morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            decoded = zbar_decode(morphed)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 9: Sharpening
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            kernel_sharpen = np.array([[-1,-1,-1], [-1, 9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel_sharpen)
            decoded = zbar_decode(sharpened)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Método 10: Inversão de cores (para casos especiais)
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            inverted = cv2.bitwise_not(gray)
            decoded = zbar_decode(inverted)
            qr_data = [d.data.decode("utf-8") for d in decoded if d and d.data]
            if qr_data:
                qr_data_found.extend(qr_data)
                pass
        except Exception as e:
            pass
        
        # Remove duplicatas mantendo ordem
        qr_unique = []
        for qr in qr_data_found:
            if qr not in qr_unique:
                qr_unique.append(qr)
        
        if qr_unique:
            pass
        else:
            pass
        
        return qr_unique
        
    except Exception as e:
        pass
        return []

def identificar_modelo_chave(chave_44):
    """
    Identifica o modelo da chave de 44 dígitos
    Posições 21-22: 59 = CF-e-SAT, 65 = NFCe
    """
    if len(chave_44) == 44 and chave_44.isdigit():
        modelo = chave_44[20:22]
        return modelo
    return None

def extrair_dados_qr_inteligente(qr_data):
    """
    Extrai dados do QR de forma inteligente baseado no modelo:
    - Modelo 59 (CF-e-SAT): 44digitos|YYYYMMDDHHMMSS|valor||codigo
    - Modelo 65 (NFCe): 44digitos|outros_parametros (SEM valor/data)
    """
    pass
    
    try:
        # Divide pelos pipes
        partes = qr_data.split("|")
        if len(partes) < 1:
            pass
            return {}
            
        chave_44 = partes[0]
        
        resultado = {}
        
        # Processa a chave de 44 dígitos
        if len(chave_44) == 44 and chave_44.isdigit():
            resultado["chave_44"] = chave_44
            
            # Identifica o modelo
            modelo = identificar_modelo_chave(chave_44)
            resultado["modelo"] = modelo
            
            if modelo == "59":
                # CF-e-SAT: pode ter valor e data no QR
                pass
                resultado = extrair_dados_qr_modelo59(qr_data)
            elif modelo == "65":
                # NFCe: QR não contém valor nem data
                pass
                resultado["observacao"] = "NFCe - valor e data devem vir do OCR ou site"
            else:
                pass
                resultado["observacao"] = f"Modelo {modelo} não reconhecido"
        else:
            pass
            
        return resultado
        
    except Exception as e:
        pass
        return {"erro": str(e)}

def extrair_dados_qr_modelo59(qr_data):
    """
    Extrai dados adicionais do QR modelo 59 no formato:
    44digitos|YYYYMMDDHHMMSS|valor||codigo
    Ex: 35251020434872000680590010147120664011776770|20251006133100|1033.61||ZwY6ld8
    """
    pass
    
    try:
        # Divide pelos pipes
        partes = qr_data.split("|")
        if len(partes) < 3:
            pass
            return {}
            
        chave_44 = partes[0]
        data_hora_str = partes[1] if len(partes) > 1 else ""
        valor_str = partes[2] if len(partes) > 2 else ""
        
        pass
        
        resultado = {}
        
        # Processa a chave de 44 dígitos
        if len(chave_44) == 44 and chave_44.isdigit():
            resultado["chave_44"] = chave_44
            resultado["modelo"] = "59"
            pass
        else:
            pass
            
        # Processa data/hora (YYYYMMDDHHMMSS - 14 dígitos)
        if data_hora_str and len(data_hora_str) == 14 and data_hora_str.isdigit():
            try:
                ano = data_hora_str[:4]
                mes = data_hora_str[4:6]
                dia = data_hora_str[6:8]
                hora = data_hora_str[8:10]
                minuto = data_hora_str[10:12]
                segundo = data_hora_str[12:14]
                
                # Formato brasileiro DD/MM/YYYY
                data_formatada = f"{dia}/{mes}/{ano}"
                hora_formatada = f"{hora}:{minuto}:{segundo}"
                
                resultado["data_emissao"] = data_formatada
                resultado["hora_emissao"] = hora_formatada
                resultado["mes_emissao"] = int(mes)
                resultado["ano_emissao"] = int(ano)
                
                pass
                
            except Exception as e:
                pass
                
        # Processa valor
        if valor_str:
            try:
                # Remove espaços e tenta converter
                valor_limpo = valor_str.strip()
                if valor_limpo:
                    # Se tem vírgula, assume formato brasileiro (1033,61)
                    if "," in valor_limpo:
                        valor_float = float(valor_limpo.replace(".", "").replace(",", "."))
                    else:
                        valor_float = float(valor_limpo)
                    
                    resultado["valor_nota"] = valor_float
                    pass
                    
            except Exception as e:
                pass
                
        pass
        return resultado
        
    except Exception as e:
        pass
        return {}


# --- Extração por fluxo: QR -> procurar 3525 -> OCR fallback ---
def extrair_chave_com_espacos(texto):
    """
    Extrai chave do formato '3525 1020...' onde podem ter espaços ou hífens.
    Também busca chaves fragmentadas em múltiplas linhas.
    """
    pass
    
    # Primeiro tenta a regex específica para chave espaçada
    match = RE_CHAVE_ESPACADA.search(texto)
    if match:
        # Junta todos os grupos de 4 dígitos
        digitos = ''.join(match.groups())
        chave_completa = "3525" + digitos
        pass
        if len(chave_completa) == 44:
            return chave_completa
    
    # Tenta busca mais flexível
    match_flex = RE_CHAVE_3525_FLEX.search(texto)
    if match_flex:
        # Remove espaços e hífens para formar a chave
        chave_raw = match_flex.group(0)
        chave_limpa = re.sub(r'[\s\-]', '', chave_raw)
        pass
        if len(chave_limpa) == 44 and chave_limpa.startswith('3525'):
            return chave_limpa
    
    # Busca manual por linhas que começam com 3525 + tentativa de continuação
    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        if '3525' in linha:
            pass
            
            # Tenta extrair só desta linha
            apenas_digitos = re.sub(r'\D', '', linha)
            if len(apenas_digitos) >= 44 and apenas_digitos.startswith('3525'):
                chave_44 = apenas_digitos[:44]
                pass
                return chave_44
            
            # Se a linha tem 3525 mas não tem 44 dígitos, procura nas próximas linhas
            elif apenas_digitos.startswith('3525') and len(apenas_digitos) < 44:
                pass
                chave_acumulada = apenas_digitos
                
                # Busca nas próximas 5 linhas para completar a chave
                for j in range(i+1, min(i+6, len(linhas))):
                    linha_seguinte = linhas[j]
                    digitos_seguinte = re.sub(r'\D', '', linha_seguinte)
                    
                    if digitos_seguinte:  # Se tem dígitos
                        chave_acumulada += digitos_seguinte
                        pass
                        
                        # Se chegou a 44 dígitos, retorna
                        if len(chave_acumulada) >= 44:
                            chave_final = chave_acumulada[:44]
                            pass
                            return chave_final
                    
                    # Para se encontrar uma linha que claramente não é continuação da chave
                    if len(linha_seguinte.strip()) > 20 and not re.search(r'\d{4}', linha_seguinte):
                        pass
                        break
                
                pass
    
    pass
    return None


def extrair_valor_total(texto):
    """
    Extrai valor específico da linha que contém 'Total R$' ou contextos de valor total
    CORRIGIDO para detectar valores totais corretamente
    """
    pass
    
    # Primeiro tenta regex específica para Total R$
    match = RE_VALOR_TOTAL.search(texto)
    if match:
        valor_str = match.group(1)
        try:
            valor_float = float(valor_str.replace(".", "").replace(",", "."))
            pass
            return valor_float
        except:
            pass
    
    # 🆕 MELHORIA: Busca por "Valor Total" seguido de valor
    import re
    match_valor_total = re.search(r'Valor\s+Total[:\s]*R?\$?\s*(\d{1,3}(?:[.,]\d{2})?)', texto, re.IGNORECASE)
    if match_valor_total:
        try:
            valor_str = match_valor_total.group(1).replace(' ', '')
            valor_float = float(valor_str.replace(".", "").replace(",", "."))
            pass
            return valor_float
        except Exception as e:
            pass
    
    # Busca manual por linhas que contêm "Total" ou "R$" com contexto
    linhas = texto.split('\n')
    for i, linha in enumerate(linhas):
        linha_upper = linha.upper()
        
        # Busca por linha com R$ seguido de valor
        if 'R$' in linha_upper and re.search(r'R\$\s*(\d{1,3}(?:[.,]\d{2})?)', linha):
            match_rs = re.search(r'R\$\s*(\d{1,3}(?:[.,]\d{2})?)', linha)
            if match_rs:
                try:
                    valor_str = match_rs.group(1).replace(' ', '')
                    valor_float = float(valor_str.replace(".", "").replace(",", "."))
                    
                    # Verifica se não está em contexto de data/hora
                    if not re.search(r'20\d{2}', linha):  # Evita anos
                        pass
                        return valor_float
                except Exception as e:
                    pass
        
        # Busca por "TOTAL" seguido de valor na próxima linha
        if 'TOTAL' in linha_upper:
            pass
            
            # Procura valor na mesma linha
            valores_linha = re.findall(r'(\d{1,3}(?:[.,]\d{2})', linha)
            if valores_linha:
                try:
                    # Pega o último valor da linha (geralmente o total)
                    valor_str = valores_linha[-1]
                    valor_float = float(valor_str.replace(".", "").replace(",", "."))
                    pass
                    return valor_float
                except Exception as e:
                    pass
            
            # Se não tem valor na mesma linha, procura nas próximas 3 linhas
            for j in range(i+1, min(i+4, len(linhas))):
                linha_seguinte = linhas[j]
                valores_seg = re.findall(r'(\d{1,3}(?:[.,]\d{2})', linha_seguinte)
                if valores_seg:
                    try:
                        valor_str = valores_seg[0]  # Primeiro valor encontrado
                        valor_float = float(valor_str.replace(".", "").replace(",", "."))
                        
                        # Verifica se não é data
                        if not re.search(r'20\d{2}', linha_seguinte):
                            pass
                            return valor_float
                    except Exception as e:
                        pass
    
    pass
    return None


def extrair_campos_de_texto(texto):
    pass
    resultado = {}
    
    # Primeiro tenta extrair chave com espaços (novo método)
    chave_espacada = extrair_chave_com_espacos(texto)
    if chave_espacada:
        resultado["chave_44"] = chave_espacada
        pass
    
    # Se não achou com espaços, tenta métodos tradicionais
    if not resultado.get("chave_44"):
        # chave 44 explícita
        m44 = RE_44.search(texto)
        if m44:
            chave = m44.group(1)
            resultado["chave_44"] = chave
            pass

        # 3525 + 44
        m3525 = RE_3525_PLUS.search(texto)
        if m3525:
            resultado["chave_44"] = m3525.group(1)
            pass

    # Primeiro tenta extrair valor do Total R$ (novo método)
    valor_total = extrair_valor_total(texto)
    if valor_total:
        resultado["valor_nota"] = valor_total
        pass

    # cnpj
    mcnpj = RE_CNPJ.search(texto)
    if mcnpj:
        resultado["cnpj"] = formatar_cnpj(mcnpj.group(1))
        pass

    # data
    mdata = RE_DATA.search(texto)
    if mdata:
        resultado["data_emissao"] = mdata.group(1)
        pass

    # valores -> 🆕 EXTRAÇÃO MELHORADA E CORRIGIDA (evita valores de data/hora)
    if not resultado.get("valor_nota"):
        # Primeiro, busca padrões mais flexíveis de valores
        import re
        
        # Padrão 1: Valores com vírgula (formato brasileiro) - FILTRADO
        valores_virgula = []
        for match in re.finditer(r'\b(\d{1,3}(?:[.,]\d{2})?)\b', texto):
            valor_str = match.group(1)
            contexto = texto[max(0, match.start()-50):match.end()+50]  # 50 chars antes e depois
            
            # FILTROS para evitar valores incorretos:
            # 1. Não deve estar em contexto de data/hora
            if not re.search(r'20\d{2}', contexto):  # Evita anos
                # 2. Não deve estar em contexto de horário
                if not re.search(r'\d{2}:\d{2}', contexto):  # Evita horários
                    # 3. Prefere contextos com R$, Total, Valor
                    if any(palavra in contexto.upper() for palavra in ['R$', 'TOTAL', 'VALOR', 'PAGAR']):
                        valores_virgula.append((valor_str, 10))  # Peso alto para contexto fiscal
                    else:
                        valores_virgula.append((valor_str, 1))   # Peso baixo para outros
        
        # Padrão 2: Valores tradicionais (também filtrados)
        vals_tradicionais = []
        for valor in RE_VALOR.findall(texto):
            # Busca contexto do valor
            pos = texto.find(valor)
            if pos != -1:
                contexto = texto[max(0, pos-50):pos+len(valor)+50]
                if not re.search(r'20\d{2}', contexto) and not re.search(r'\d{2}:\d{2}', contexto):
                    if any(palavra in contexto.upper() for palavra in ['R$', 'TOTAL', 'VALOR']):
                        vals_tradicionais.append((valor, 10))
                    else:
                        vals_tradicionais.append((valor, 1))
        
        # Combina todos os valores com seus pesos
        todos_valores_com_peso = valores_virgula + vals_tradicionais
        
        if todos_valores_com_peso:
            pass
            try:
                # Converte e ordena por peso (valores em contexto fiscal primeiro)
                valsf = []
                for v, peso in todos_valores_com_peso:
                    try:
                        # Normaliza formato (vírgula para ponto)
                        v_norm = v.replace(".", "").replace(",", ".")
                        val_float = float(v_norm)
                        # Filtro: valores entre R$ 0,01 e R$ 99.999,99 (plausíveis para NFCe)
                        if 0.01 <= val_float <= 99999.99:
                            valsf.append((val_float, peso))
                    except:
                        continue
                
                if valsf:
                    # Estratégia: ordena por peso (contexto fiscal) e depois por valor
                    valsf_ordenados = sorted(valsf, key=lambda x: (x[1], x[0]), reverse=True)
                    resultado["valor_nota"] = valsf_ordenados[0][0]  # Pega o melhor valor
                    pass
            except Exception as e:
                pass

    # sat
    msat = RE_SAT.search(texto)
    if msat:
        resultado["sat"] = msat.group(1)
        pass

    # numero do cupom
    mnum = RE_NUM_CUPOM.search(texto)
    if mnum:
        resultado["numero_cupom"] = mnum.group(1)
        pass

    pass
    return resultado

def avaliar_estagio_resolucao(resultado):
    """
    Avalia se o arquivo foi resolvido no primeiro estágio ou precisa de processamento adicional.
    
    Critérios para "resolvido":
    - Tem chave (id_cupom preenchido)
    - Tem valor (valor_nota preenchido)  
    - Tem data (data_emissao preenchida)
    
    Estágios possíveis:
    - "1_resolvido": Todos os campos essenciais extraídos com sucesso
    - "1_parcial": Alguns campos extraídos, mas faltam dados essenciais
    - "1_sem_dados": Nenhum dado essencial encontrado
    """
    tem_chave = bool(resultado.get("id_cupom"))
    tem_valor = bool(resultado.get("valor_nota"))
    tem_data = bool(resultado.get("data_emissao"))
    
    pass
    
    # NOVO CRITÉRIO: Se tem chave + valor, já considera resolvido (data é opcional)
    if tem_chave and tem_valor:
        estagio = "1_resolvido"
        pass
    
    # Parcial: tem chave OU valor (mas não ambos)
    elif tem_chave or tem_valor:
        estagio = "1_parcial"
        campos_faltando = []
        if not tem_chave: campos_faltando.append("chave")
        if not tem_valor: campos_faltando.append("valor")
        if not tem_data: campos_faltando.append("data")
        pass
    
    # Sem dados: nenhum campo essencial
    else:
        estagio = "1_sem_dados"
        pass
    
    pass
    return estagio


def calcular_score_resultado(resultado):
    """
    Calcula um score para comparar qualidade entre resultados de estágios.
    Score maior = resultado melhor
    """
    score = 0
    
    # Chave vale 100 pontos
    if resultado.get("id_cupom"):
        score += 100
    
    # Valor vale 80 pontos
    if resultado.get("valor_nota"):
        score += 80
    
    # Data vale 20 pontos
    if resultado.get("data_emissao"):
        score += 20
    
    # CNPJ vale 10 pontos
    if resultado.get("cnpj"):
        score += 10
    
    # Status específicos valem pontos extras
    status = resultado.get("status", "")
    if "chave_extraida_qr" in status:
        score += 50  # QR é mais confiável
    elif "chave_extraida_ocr" in status:
        score += 30
    elif "chave_extraida_estagio2" in status:
        score += 25
    elif "dados_parciais" in status:
        score += 5
    
    return score


class ProcessadorNFCe7Estagios:
    """
    Processador de NFCe com arquitetura de 7 estágios:
    1. QR Code → Extração de dados do QR
    2. Código de Barras → Leitura alternativa (futuro)
    3. OCR → Extração de texto da imagem
    4. Validação → Verificação de chave e DV
    5. HTML → Consulta no site da Fazenda
    6. Melhoramento de Imagem → Técnicas de pré-processamento
    7. Biblioteca Alternativa → Outras libs de QR/OCR (futuro)
    """
    
    def __init__(self, debug=True):  # Debug desabilitado por padrão para produção
        self.resultados_estagios = {}
        self.melhor_resultado = None
        self.debug = debug
        # Log estruturado para cada arquivo
        self.log_arquivo_atual = None
    
    def iniciar_log_arquivo(self, nome_arquivo):
        """Inicia um novo log estruturado para o arquivo"""
        self.log_arquivo_atual = {
            'arquivo': nome_arquivo,
            'estagio_1': 'null',
            'estagio_2': 'null', 
            'estagio_3': 'null',
            'estagio_4': 'null',
            'estagio_5': 'null',
            'estagio_6': 'null',
            'estagio_7': 'null',
            'resultado': 'não resolvido'
        }
    
    def atualizar_log_estagio(self, estagio, status):
        """Atualiza o status de um estágio específico"""
        if self.log_arquivo_atual:
            self.log_arquivo_atual[f'estagio_{estagio}'] = status
    
    def finalizar_log_arquivo(self, resolvido=False):
        """Finaliza o log do arquivo"""
        if self.log_arquivo_atual:
            self.log_arquivo_atual['resultado'] = 'resolvido' if resolvido else 'não resolvido'
            return self.log_arquivo_atual.copy()
        return None

    def log_debug(self, estagio, mensagem):
        """Log de debug para acompanhar o processo"""
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Mais precisão
            print(f"[{timestamp}] 🔧 ESTÁGIO {estagio}: {mensagem}")
    
    def processar_arquivo_7_estagios(self, file_path):
        """
        Processa um arquivo através dos 7 estágios e retorna o melhor resultado
        Otimizado: interrompe processamento ao obter todos os campos essenciais de fonte confiável
        """
        nome_arquivo = os.path.basename(file_path)
        self.iniciar_log_arquivo(nome_arquivo)
        if self.debug:
            print(f"\n🚀 PROCESSAMENTO EM 7 ESTÁGIOS - DEBUG DETALHADO")
            print(f"Arquivo: {nome_arquivo}")
            print("=" * 80)
        self.resultados_estagios = {}

        # ESTÁGIO 1: QR CODE
        resultado_qr = self.estagio_1_qr_code(file_path)
        self.selecionar_melhor_resultado()
        if resultado_qr.get('chave') and resultado_qr.get('valor') and resultado_qr.get('data'):
            # Se já extraiu tudo do QR, interrompe
            if self.debug:
                print("Todos os campos essenciais extraídos do QR. Interrompendo processamento.")
            tem_chave = resultado_qr.get('chave') is not None
            tem_valor = resultado_qr.get('valor') is not None
            tem_data = resultado_qr.get('data') is not None
            resolvido = tem_chave and tem_valor and tem_data
            log_arquivo = self.finalizar_log_arquivo(resolvido)
            resultado_com_log = self.melhor_resultado.copy()
            resultado_com_log['log_arquivo'] = log_arquivo
            return resultado_com_log

        # Se só extraiu a chave, tenta site antes de OCR
        if resultado_qr.get('chave') and (not resultado_qr.get('valor') or not resultado_qr.get('data')):
            # Validação e consulta site
            self.estagio_4_validacao(file_path)
            self.estagio_5_html(file_path)
            self.selecionar_melhor_resultado()
            if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
                if self.debug:
                    print("Campos essenciais extraídos após consulta ao site. Interrompendo processamento.")
                tem_chave = self.melhor_resultado.get('chave') is not None
                tem_valor = self.melhor_resultado.get('valor') is not None
                tem_data = self.melhor_resultado.get('data') is not None
                resolvido = tem_chave and tem_valor and tem_data
                log_arquivo = self.finalizar_log_arquivo(resolvido)
                resultado_com_log = self.melhor_resultado.copy()
                resultado_com_log['log_arquivo'] = log_arquivo
                return resultado_com_log

        # ESTÁGIO 2: CÓDIGO DE BARRAS
        resultado_barcode = self.estagio_2_codigo_barras(file_path)
        self.selecionar_melhor_resultado()
        if resultado_barcode.get('chave'):
            self.estagio_4_validacao(file_path)
            self.estagio_5_html(file_path)
            self.selecionar_melhor_resultado()
            if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
                if self.debug:
                    print("Campos essenciais extraídos após código de barras e site. Interrompendo processamento.")
                tem_chave = self.melhor_resultado.get('chave') is not None
                tem_valor = self.melhor_resultado.get('valor') is not None
                tem_data = self.melhor_resultado.get('data') is not None
                resolvido = tem_chave and tem_valor and tem_data
                log_arquivo = self.finalizar_log_arquivo(resolvido)
                resultado_com_log = self.melhor_resultado.copy()
                resultado_com_log['log_arquivo'] = log_arquivo
                return resultado_com_log

        # ESTÁGIO 3: OCR
        resultado_ocr = self.estagio_3_ocr(file_path)
        self.selecionar_melhor_resultado()
        if resultado_ocr.get('chave') and resultado_ocr.get('valor') and resultado_ocr.get('data'):
            self.estagio_4_validacao(file_path)
            self.estagio_5_html(file_path)
            self.selecionar_melhor_resultado()
            if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
                if self.debug:
                    print("Campos essenciais extraídos após OCR, validação e site. Interrompendo processamento.")
                tem_chave = self.melhor_resultado.get('chave') is not None
                tem_valor = self.melhor_resultado.get('valor') is not None
                tem_data = self.melhor_resultado.get('data') is not None
                resolvido = tem_chave and tem_valor and tem_data
                log_arquivo = self.finalizar_log_arquivo(resolvido)
                resultado_com_log = self.melhor_resultado.copy()
                resultado_com_log['log_arquivo'] = log_arquivo
                return resultado_com_log

        # ESTÁGIO 4: VALIDAÇÃO (caso não tenha sido feita)
        self.estagio_4_validacao(file_path)
        # ESTÁGIO 5: HTML (caso não tenha sido feita)
        self.estagio_5_html(file_path)
        self.selecionar_melhor_resultado()
        if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
            if self.debug:
                print("Campos essenciais extraídos após validação e site. Interrompendo processamento.")
            tem_chave = self.melhor_resultado.get('chave') is not None
            tem_valor = self.melhor_resultado.get('valor') is not None
            tem_data = self.melhor_resultado.get('data') is not None
            resolvido = tem_chave and tem_valor and tem_data
            log_arquivo = self.finalizar_log_arquivo(resolvido)
            resultado_com_log = self.melhor_resultado.copy()
            resultado_com_log['log_arquivo'] = log_arquivo
            return resultado_com_log

        # ESTÁGIO 6: MELHORAMENTO DE IMAGEM
        resultado_melhoramento = self.estagio_6_melhoramento_imagem(file_path)
        self.selecionar_melhor_resultado()
        # Se obteve a chave após o melhoramento, volta para validação e site
        if self.melhor_resultado.get('chave'):
            self.estagio_4_validacao(file_path)
            self.estagio_5_html(file_path)
            self.selecionar_melhor_resultado()
            if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
                if self.debug:
                    print("Campos essenciais extraídos após melhoramento, validação e site. Interrompendo processamento.")
                tem_chave = self.melhor_resultado.get('chave') is not None
                tem_valor = self.melhor_resultado.get('valor') is not None
                tem_data = self.melhor_resultado.get('data') is not None
                resolvido = tem_chave and tem_valor and tem_data
                log_arquivo = self.finalizar_log_arquivo(resolvido)
                resultado_com_log = self.melhor_resultado.copy()
                resultado_com_log['log_arquivo'] = log_arquivo
                return resultado_com_log

        # ESTÁGIO 7: BIBLIOTECA ALTERNATIVA
        resultado_alternativo = self.estagio_7_biblioteca_alternativa(file_path)
        self.selecionar_melhor_resultado()
        # Finaliza log do arquivo com status de resolvido
        tem_chave = self.melhor_resultado.get('chave') is not None
        tem_valor = self.melhor_resultado.get('valor') is not None
        tem_data = self.melhor_resultado.get('data') is not None
        resolvido = tem_chave and tem_valor and tem_data
        log_arquivo = self.finalizar_log_arquivo(resolvido)
        resultado_com_log = self.melhor_resultado.copy()
        resultado_com_log['log_arquivo'] = log_arquivo
        return resultado_com_log
    
    def estagio_1_qr_code(self, file_path):
        """ESTÁGIO 1: Extração e processamento de dados do QR Code"""
        self.log_debug(1, "Iniciando leitura de QR Code")
        
        resultado = {
            'sucesso': False,
            'score': 0,
            'chave': None,
            'valor': None,
            'data': None,
            'qrs': []
        }
        
        try:
            qrs = read_qr_from_image(file_path)
            resultado['qrs'] = qrs
            
            if qrs:
                self.log_debug(1, f"✅ {len(qrs)} QR(s) encontrado(s)")
                self.atualizar_log_estagio(1, 'ok')
                
                for qr in qrs:
                    # Extrai parâmetro se é URL
                    parametro_qr = qr
                    if "?p=" in qr:
                        parametro_qr = qr.split("?p=")[1]
                    
                    # Processa com lógica inteligente
                    if "|" in parametro_qr:
                        dados_qr = extrair_dados_qr_inteligente(parametro_qr)
                        if dados_qr.get("chave_44"):
                            resultado['chave'] = dados_qr["chave_44"]
                            resultado['score'] += 100  # Chave = 100 pontos
                            resultado['sucesso'] = True
                            self.log_debug(1, f"✅ Chave extraída: {resultado['chave']}")
                        
                        # Para modelo 59, pode ter valor e data
                        if dados_qr.get("modelo") == "59":
                            if dados_qr.get("valor_nota"):
                                resultado['valor'] = dados_qr["valor_nota"]
                                resultado['score'] += 80
                                self.log_debug(1, f"✅ Valor QR: R$ {resultado['valor']}")
                            
                            if dados_qr.get("data_emissao"):
                                resultado['data'] = dados_qr["data_emissao"]
                                resultado['score'] += 20
                                self.log_debug(1, f"✅ Data QR: {resultado['data']}")
                    
                    # Se encontrou chave, para no primeiro QR
                    if resultado['chave']:
                        break
                
                self.log_debug(1, f"Score final: {resultado['score']} pontos")
            else:
                self.log_debug(1, "❌ Nenhum QR encontrado")
                self.atualizar_log_estagio(1, 'falhou')
            
        except Exception as e:
            self.log_debug(1, f"❌ Erro: {e}")
            self.atualizar_log_estagio(1, 'erro')
            resultado['erro'] = str(e)
        
        self.resultados_estagios[1] = resultado
        return resultado
    
    def estagio_2_codigo_barras(self, file_path):
        """ESTÁGIO 2: Leitura de código de barras (implementado)"""
        self.log_debug(2, "Iniciando leitura de código de barras")
        resultado = {
            'sucesso': False,
            'score': 0,
            'chave': None,
            'barcodes': [],
            'mensagem': ''
        }
        try:
            import cv2
            from pyzbar.pyzbar import decode as zbar_decode
            img = cv2.imread(file_path)
            if img is None:
                self.log_debug(2, "❌ Imagem não encontrada")
                resultado['mensagem'] = 'Imagem não encontrada'
                self.atualizar_log_estagio(2, 'falhou')
                self.resultados_estagios[2] = resultado
                return resultado
            # Tenta encontrar todos os códigos de barras
            decoded = zbar_decode(img)
            barcodes = [d.data.decode('utf-8') for d in decoded if d.type in ['CODE128', 'CODE39', 'EAN13', 'EAN8', 'ITF', 'CODE93']]
            resultado['barcodes'] = barcodes
            self.log_debug(2, f"Encontrados {len(barcodes)} código(s) de barras")
            # Junta partes se necessário (ex: 2 partes de 22 dígitos)
            chaves_possiveis = []
            for b in barcodes:
                b_digits = ''.join(filter(str.isdigit, b))
                if len(b_digits) == 44:
                    chaves_possiveis.append(b_digits)
            # Se não achou, tenta juntar partes
            if not chaves_possiveis and len(barcodes) >= 2:
                for i in range(len(barcodes)):
                    for j in range(i+1, len(barcodes)):
                        b1 = ''.join(filter(str.isdigit, barcodes[i]))
                        b2 = ''.join(filter(str.isdigit, barcodes[j]))
                        if len(b1) + len(b2) == 44:
                            chaves_possiveis.append(b1 + b2)
            # Seleciona chave válida
            for chave in chaves_possiveis:
                if len(chave) == 44:
                    resultado['chave'] = chave
                    resultado['sucesso'] = True
                    resultado['score'] = 95
                    self.log_debug(2, f"✅ Chave extraída do código de barras: {chave}")
                    self.atualizar_log_estagio(2, 'ok')
                    break
            if not resultado['sucesso']:
                resultado['mensagem'] = 'Nenhuma chave válida encontrada'
                self.atualizar_log_estagio(2, 'falhou')
        except Exception as e:
            resultado['mensagem'] = f'Erro: {e}'
            self.log_debug(2, f"❌ Erro: {e}")
            self.atualizar_log_estagio(2, 'erro')
        self.resultados_estagios[2] = resultado
        return resultado
    
    def estagio_3_ocr(self, file_path):
        """ESTÁGIO 3: Extração de texto via OCR"""
        self.log_debug(3, "Iniciando OCR de texto")
        
        resultado = {
            'sucesso': False,
            'score': 0,
            'chave': None,
            'valor': None,
            'data': None,
            'texto': ""
        }
        
        try:
            texto = ocr_text_from_image(file_path)
            resultado['texto'] = texto
            
            if texto and len(texto) > 50:  # Mínimo de 50 caracteres
                self.log_debug(3, f"✅ Texto extraído: {len(texto)} caracteres")
                self.atualizar_log_estagio(3, 'ok')
                
                # Extrai campos do texto
                campos = extrair_campos_de_texto(texto)
                
                if campos.get('chave_44'):
                    resultado['chave'] = campos['chave_44']
                    resultado['score'] += 90  # Menor que QR
                    self.log_debug(3, f"✅ Chave OCR: {resultado['chave']}")
                
                if campos.get('valor_nota'):
                    resultado['valor'] = campos['valor_nota']
                    resultado['score'] += 70  # Menor que QR
                    self.log_debug(3, f"✅ Valor OCR: R$ {resultado['valor']}")
                
                if campos.get('data_emissao'):
                    resultado['data'] = campos['data_emissao']
                    resultado['score'] += 15  # Menor que QR
                    self.log_debug(3, f"✅ Data OCR: {resultado['data']}")
                
                resultado['campos'] = campos
                resultado['sucesso'] = True
                self.log_debug(3, f"Score final: {resultado['score']} pontos")
            else:
                self.log_debug(3, "❌ Texto insuficiente extraído")
                self.atualizar_log_estagio(3, 'falhou')
            
        except Exception as e:
            self.log_debug(3, f"❌ Erro: {e}")
            self.atualizar_log_estagio(3, 'erro')
            resultado['erro'] = str(e)
        
        self.resultados_estagios[3] = resultado
        return resultado
    
    def estagio_4_validacao(self, file_path):
        """ESTÁGIO 4: Validação de chave e cálculo de DV"""
        self.log_debug(4, "Validando chaves encontradas")
        
        chaves_para_validar = []
        
        # Coleta chaves dos estágios anteriores
        for i in [1, 3]:  # QR e OCR
            if i in self.resultados_estagios and self.resultados_estagios[i].get('chave'):
                chaves_para_validar.append(self.resultados_estagios[i]['chave'])
        
        resultado = {
            'sucesso': False,
            'score': 0,
            'chaves_validadas': {},
            'melhor_chave': None
        }
        
        if chaves_para_validar:
            try:
                for chave in set(chaves_para_validar):  # Remove duplicatas
                    dv_valido = calcular_dv_chave(chave)
                    resultado['chaves_validadas'][chave] = dv_valido
                    
                    if dv_valido:
                        resultado['melhor_chave'] = chave
                        resultado['sucesso'] = True
                        resultado['score'] = 50  # Bonus por chave válida
                        self.atualizar_log_estagio(4, 'ok')
                        self.log_debug(4, f"✅ Chave válida: {chave}")
                        break
                    else:
                        self.log_debug(4, f"❌ Chave inválida: {chave}")
                
                if not resultado['sucesso']:
                    self.log_debug(4, "❌ Nenhuma chave passou na validação DV")
                    self.atualizar_log_estagio(4, 'falhou')
            
            except Exception as e:
                self.log_debug(4, f"❌ Erro na validação: {e}")
                self.atualizar_log_estagio(4, 'erro')
                resultado['erro'] = str(e)
        else:
            self.log_debug(4, "❌ Nenhuma chave encontrada para validar")
            self.atualizar_log_estagio(4, 'null')
        
        self.resultados_estagios[4] = resultado
        return resultado
    
    def estagio_5_html(self, file_path):
        """ESTÁGIO 5: Consulta no site da Fazenda SP"""
        self.log_debug(5, "🌐 INICIANDO consulta no site da Fazenda SP")
        
        qrs = None
        if 1 in self.resultados_estagios and self.resultados_estagios[1].get('qrs'):
            qrs = self.resultados_estagios[1]['qrs']
            self.log_debug(5, f"✅ QRs disponíveis: {len(qrs)} encontrados")
            for i, qr in enumerate(qrs):
                self.log_debug(5, f"   QR {i+1}: {qr[:100]}...")
        else:
            self.log_debug(5, "❌ Nenhum QR disponível dos estágios anteriores")
        
        resultado = {
            'sucesso': False,
            'score': 0,
            'dados_site': None,
            'valor': None,
            'data': None
        }
        
        if qrs:
            try:
                self.log_debug(5, f"🔍 Consultando site com QR: {qrs[0][:50]}...")
                dados_site = consultar_nfce_fazenda_sp(qrs[0])
                
                self.log_debug(5, f"📋 Resposta do site: {dados_site is not None}")
                
                if dados_site:
                    self.log_debug(5, "✅ Dados obtidos do site com sucesso")
                    self.atualizar_log_estagio(5, 'ok')
                    
                    resultado['sucesso'] = True
                    resultado['dados_site'] = dados_site
                    resultado['score'] = 30  # Bonus por dados do site
                    
                    # Extrai valor e data do site se disponível (CORRIGIDO: usar chaves corretas)
                    if dados_site.get('valor_site'):
                        resultado['valor'] = dados_site['valor_site']
                        resultado['score'] += 25
                    
                    if dados_site.get('data_site'):
                        resultado['data'] = dados_site['data_site']
                        resultado['score'] += 10
                    
                    self.log_debug(5, f"🎯 Score final do estágio 5: {resultado['score']}")
                else:
                    self.log_debug(5, "❌ Site retornou dados vazios ou nulos")
                    self.atualizar_log_estagio(5, 'falhou')
            
            except Exception as e:
                self.log_debug(5, f"❌ Erro na consulta: {e}")
                self.atualizar_log_estagio(5, 'erro')
                resultado['erro'] = str(e)
                resultado['erro'] = str(e)
        else:
            self.log_debug(5, "❌ Nenhum QR disponível para consulta")
        
        self.resultados_estagios[5] = resultado
        return resultado
    
    def estagio_6_melhoramento_imagem(self, file_path):
        """ESTÁGIO 6: Melhoramento de imagem com múltiplas técnicas e re-execução"""
        self.log_debug(6, "🎨 INICIANDO melhoramento avançado de imagem")
        
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageEnhance, ImageFilter
            import os
            
            # Verifica se já temos resultado satisfatório
            if self.melhor_resultado and self.melhor_resultado.get('score', 0) >= 100:
                self.log_debug(6, "✅ Resultado já satisfatório, pulando melhoramento")
                resultado = {'sucesso': True, 'score': 0, 'mensagem': 'Resultado já satisfatório'}
                self.resultados_estagios[6] = resultado
                self.atualizar_log_estagio(6, 'ok')
                return resultado
            
            # Lista de técnicas de melhoramento - TODAS RESTAURADAS
            tecnicas_melhoramento = [
                "otsu_threshold",
                "adaptive_threshold", 
                "contrast_enhancement",
                "noise_reduction",
                "sharpening",
                "histogram_equalization",
                "morphological_operations",
                "bilateral_filter"
            ]
            
            melhor_score_anterior = self.melhor_resultado.get('score', 0) if self.melhor_resultado else 0
            melhor_resultado_melhorado = None
            melhor_tecnica = None
            
            for i, tecnica in enumerate(tecnicas_melhoramento):
                self.log_debug(6, f"🎨 Testando técnica {i+1}/{len(tecnicas_melhoramento)}: {tecnica}")

                # Aplica técnica de melhoramento
                imagem_melhorada_path = self.aplicar_tecnica_melhoramento(file_path, tecnica)

                if imagem_melhorada_path:
                    # Re-executa estágios 1-3 com imagem melhorada
                    score_melhorado = self.reexecutar_estagios_com_imagem_melhorada(imagem_melhorada_path)

                    self.log_debug(6, f"🎨 Técnica {tecnica}: Score {score_melhorado} (anterior: {melhor_score_anterior})")

                    # Se melhorou, salva como melhor resultado
                    if score_melhorado > melhor_score_anterior:
                        melhor_score_anterior = score_melhorado
                        melhor_resultado_melhorado = self.melhor_resultado.copy()
                        melhor_tecnica = tecnica
                        self.log_debug(6, f"🎯 MELHORIA! Nova técnica vencedora: {tecnica} (Score: {score_melhorado})")
                    else:
                        self.log_debug(6, f"⚠️  Técnica {tecnica} não melhorou (Score {score_melhorado} <= {melhor_score_anterior})")

                    # Após cada melhoramento, tenta validação e site
                    if self.melhor_resultado.get('chave'):
                        self.estagio_4_validacao(imagem_melhorada_path)
                        self.estagio_5_html(imagem_melhorada_path)
                        self.selecionar_melhor_resultado()
                        if self.melhor_resultado.get('chave') and self.melhor_resultado.get('valor') and self.melhor_resultado.get('data'):
                            self.log_debug(6, f"✅ Dados essenciais extraídos após melhoramento, validação e site com {tecnica}. Encerrando processamento.")
                            # Limpa arquivo temporário
                            try:
                                os.remove(imagem_melhorada_path)
                            except:
                                pass
                            self.atualizar_log_estagio(6, 'ok')
                            return {
                                'sucesso': True,
                                'score': 20,
                                'tecnica_vencedora': tecnica,
                                'score_final': melhor_score_anterior,
                                'mensagem': f'Imagem melhorada com {tecnica} e dados extraídos com sucesso'
                            }

                    # Limpa arquivo temporário
                    try:
                        os.remove(imagem_melhorada_path)
                    except:
                        pass

                # Para early se conseguiu score perfeito
                if melhor_score_anterior >= 100:
                    self.log_debug(6, f"🎯 Score perfeito alcançado com {tecnica}! Parando iterações.")
                    break
            
            # Resultado final do estágio 6
            if melhor_resultado_melhorado:
                self.melhor_resultado = melhor_resultado_melhorado
                self.log_debug(6, f"✅ SUCESSO! Melhor técnica: {melhor_tecnica} (Score final: {melhor_score_anterior})")
                resultado = {
                    'sucesso': True,
                    'score': 20,  # Bônus por melhoramento
                    'tecnica_vencedora': melhor_tecnica,
                    'score_final': melhor_score_anterior,
                    'mensagem': f'Imagem melhorada com {melhor_tecnica}'
                }
                self.atualizar_log_estagio(6, 'ok')
            else:
                self.log_debug(6, "❌ Nenhuma técnica conseguiu melhorar o resultado")
                resultado = {
                    'sucesso': False,
                    'score': 0,
                    'mensagem': 'Nenhuma técnica de melhoramento foi efetiva'
                }
                self.atualizar_log_estagio(6, 'falhou')
            
            self.resultados_estagios[6] = resultado
            return resultado
            
        except Exception as e:
            self.log_debug(6, f"❌ Erro no melhoramento: {str(e)}")
            resultado = {'sucesso': False, 'score': 0, 'erro': str(e)}
            self.resultados_estagios[6] = resultado
            self.atualizar_log_estagio(6, 'erro')
            return resultado
    
    def aplicar_tecnica_melhoramento(self, file_path, tecnica):
        """Aplica uma técnica específica de melhoramento na imagem"""
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageEnhance, ImageFilter
            import tempfile
            import os
            
            # Carrega imagem original
            img = cv2.imread(file_path)
            if img is None:
                return None
            
            # Aplica técnica específica
            if tecnica == "otsu_threshold":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                _, img_melhorada = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
            elif tecnica == "adaptive_threshold":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img_melhorada = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                
            elif tecnica == "contrast_enhancement":
                pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                enhancer = ImageEnhance.Contrast(pil_img)
                pil_enhanced = enhancer.enhance(2.0)
                img_melhorada = cv2.cvtColor(np.array(pil_enhanced), cv2.COLOR_RGB2BGR)
                
            elif tecnica == "noise_reduction":
                img_melhorada = cv2.medianBlur(img, 3)
                
            elif tecnica == "sharpening":
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                img_melhorada = cv2.filter2D(img, -1, kernel)
                
            elif tecnica == "histogram_equalization":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img_melhorada = cv2.equalizeHist(gray)
                
            elif tecnica == "morphological_operations":
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                kernel = np.ones((2,2), np.uint8)
                img_melhorada = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
                
            elif tecnica == "bilateral_filter":
                img_melhorada = cv2.bilateralFilter(img, 9, 75, 75)
                
            else:
                return None
            
            # Salva imagem temporária
            temp_dir = tempfile.gettempdir()
            temp_filename = f"temp_melhorada_{tecnica}_{os.path.basename(file_path)}"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            cv2.imwrite(temp_path, img_melhorada)
            return temp_path
            
        except Exception as e:
            return None
    
    def reexecutar_estagios_com_imagem_melhorada(self, imagem_melhorada_path):
        """Re-executa estágios 1-3 com imagem melhorada e retorna o melhor score"""
        try:
            # Cria uma nova instância temporária para teste
            temp_processador = ProcessadorNFCe7Estagios(debug=False)  # Debug False para não confundir logs
            
            # Re-executa estágios na instância temporária
            resultado_qr = temp_processador.estagio_1_qr_code(imagem_melhorada_path)
            resultado_ocr = temp_processador.estagio_3_ocr(imagem_melhorada_path)
            
            # Debug dos resultados individuais
            self.log_debug(6, f"🔍 QR Result: {resultado_qr}")
            self.log_debug(6, f"🔍 OCR Result: {resultado_ocr}")
            
            # Calcula melhor resultado temporário
            temp_processador.selecionar_melhor_resultado()
            novo_resultado = temp_processador.melhor_resultado
            novo_score = novo_resultado.get('score_total', 0) if novo_resultado else 0  # CORREÇÃO: usar score_total
            score_atual = self.melhor_resultado.get('score_total', 0) if self.melhor_resultado else 0  # CORREÇÃO: usar score_total
            
            self.log_debug(6, f"📊 Comparação: Novo score={novo_score}, Score atual={score_atual}")
            self.log_debug(6, f"📊 Novo resultado: {novo_resultado}")
            
            # Se melhorou, salva os resultados na instância principal
            if novo_score > score_atual:
                self.log_debug(6, f"✅ MELHOROU! Salvando resultado com score {novo_score}")
                self.resultados_estagios.update(temp_processador.resultados_estagios)
                self.melhor_resultado = temp_processador.melhor_resultado.copy()
                
            return novo_score
            
        except Exception as e:
            self.log_debug(6, f"❌ Erro na re-execução: {e}")
            import traceback
            self.log_debug(6, f"❌ Traceback: {traceback.format_exc()}")
            return 0
    
    def estagio_7_biblioteca_alternativa(self, file_path):
        """ESTÁGIO 7: Leitura usando bibliotecas alternativas (zxing, easyocr)"""
        self.log_debug(7, "Iniciando leitura alternativa com bibliotecas externas")
        resultado = {
            'sucesso': False,
            'score': 0,
            'chave': None,
            'valor': None,
            'data': None,
            'mensagem': '',
            'qr': None,
            'barcode': None,
            'ocr_text': None
        }
        try:
            # ZXing para QR e código de barras
            try:
                from pyzxing import BarCodeReader
                reader = BarCodeReader()
                out = reader.decode(file_path)
                qr_codes = [r['raw'] for r in out if r['type'] == 'QR_CODE'] if out else []
                barcodes = [r['raw'] for r in out if r['type'] != 'QR_CODE'] if out else []
                resultado['qr'] = qr_codes
                resultado['barcode'] = barcodes
                self.log_debug(7, f"ZXing: {len(qr_codes)} QR(s), {len(barcodes)} código(s) de barras")
                # Busca chave de acesso nos códigos de barras
                chaves_possiveis = []
                for b in barcodes:
                    b_digits = ''.join(filter(str.isdigit, b))
                    if len(b_digits) == 44:
                        chaves_possiveis.append(b_digits)
                if not chaves_possiveis and len(barcodes) >= 2:
                    for i in range(len(barcodes)):
                        for j in range(i+1, len(barcodes)):
                            b1 = ''.join(filter(str.isdigit, barcodes[i]))
                            b2 = ''.join(filter(str.isdigit, barcodes[j]))
                            if len(b1) + len(b2) == 44:
                                chaves_possiveis.append(b1 + b2)
                for chave in chaves_possiveis:
                    if len(chave) == 44:
                        resultado['chave'] = chave
                        resultado['sucesso'] = True
                        resultado['score'] += 100
                        self.log_debug(7, f"✅ Chave alternativa (ZXing): {chave}")
                        break
            except Exception as e:
                self.log_debug(7, f"ZXing não disponível: {e}")
            # EasyOCR para OCR alternativo
            try:
                import easyocr
                reader = easyocr.Reader(['pt', 'en'])
                ocr_result = reader.readtext(file_path, detail=0)
                texto_ocr = '\n'.join(ocr_result)
                resultado['ocr_text'] = texto_ocr
                self.log_debug(7, f"EasyOCR: {len(texto_ocr)} caracteres extraídos")
                # Busca valor e data no texto
                campos = extrair_campos_de_texto(texto_ocr)
                if campos.get('valor_nota'):
                    resultado['valor'] = campos['valor_nota']
                    resultado['score'] += 80
                if campos.get('data_emissao'):
                    resultado['data'] = campos['data_emissao']
                    resultado['score'] += 20
                if campos.get('chave_44') and not resultado['chave']:
                    resultado['chave'] = campos['chave_44']
                    resultado['score'] += 90
                    resultado['sucesso'] = True
                    self.log_debug(7, f"✅ Chave alternativa (EasyOCR): {campos['chave_44']}")
            except Exception as e:
                self.log_debug(7, f"EasyOCR não disponível: {e}")
            if resultado['sucesso']:
                self.atualizar_log_estagio(7, 'ok')
            else:
                resultado['mensagem'] = 'Nenhum dado relevante extraído por bibliotecas alternativas'
                self.atualizar_log_estagio(7, 'falhou')
        except Exception as e:
            resultado['mensagem'] = f'Erro: {e}'
            self.log_debug(7, f"❌ Erro: {e}")
            self.atualizar_log_estagio(7, 'erro')
        self.resultados_estagios[7] = resultado
        return resultado
    
    def selecionar_melhor_resultado(self):
        """Seleciona o melhor resultado combinando dados de todos os estágios"""
        if self.debug:
            print(f"\n📊 ANÁLISE FINAL - SELEÇÃO DO MELHOR RESULTADO")
            print("=" * 50)
        
        # Calcula scores
        for i in range(1, 8):
            if i in self.resultados_estagios:
                score = self.resultados_estagios[i].get('score', 0)
                sucesso = self.resultados_estagios[i].get('sucesso', False)
                if self.debug:
                    status = "✅" if sucesso else "❌"
                    print(f"Estágio {i}: {status} Score: {score} pontos")
        
        # Monta resultado final
        resultado_final = {
            'chave': None,
            'valor': None,
            'data': None,
            'score_total': 0,
            'estagios_bem_sucedidos': [],
            'fonte_chave': None,
            'fonte_valor': None,
            'fonte_data': None
        }
        
        # Prioriza chave validada do estágio 4
        if 4 in self.resultados_estagios and self.resultados_estagios[4].get('melhor_chave'):
            resultado_final['chave'] = self.resultados_estagios[4]['melhor_chave']
            resultado_final['fonte_chave'] = 'validacao'
        # Senão, pega do QR (estágio 1)
        elif 1 in self.resultados_estagios and self.resultados_estagios[1].get('chave'):
            resultado_final['chave'] = self.resultados_estagios[1]['chave']
            resultado_final['fonte_chave'] = 'qr'
        # Por último, do OCR (estágio 3)
        elif 3 in self.resultados_estagios and self.resultados_estagios[3].get('chave'):
            resultado_final['chave'] = self.resultados_estagios[3]['chave']
            resultado_final['fonte_chave'] = 'ocr'
        
        # Para valor: prioriza QR (modelo 59), depois OCR, depois site
        for fonte_id, fonte_nome in [(1, 'qr'), (3, 'ocr'), (5, 'site')]:
            if fonte_id in self.resultados_estagios and self.resultados_estagios[fonte_id].get('valor'):
                resultado_final['valor'] = self.resultados_estagios[fonte_id]['valor']
                resultado_final['fonte_valor'] = fonte_nome
                break
        
        # Para data: mesma lógica do valor
        for fonte_id, fonte_nome in [(1, 'qr'), (3, 'ocr'), (5, 'site')]:
            if fonte_id in self.resultados_estagios and self.resultados_estagios[fonte_id].get('data'):
                resultado_final['data'] = self.resultados_estagios[fonte_id]['data']
                resultado_final['fonte_data'] = fonte_nome
                break
        
        # Calcula score total
        for i in range(1, 8):
            if i in self.resultados_estagios:
                resultado_final['score_total'] += self.resultados_estagios[i].get('score', 0)
                if self.resultados_estagios[i].get('sucesso'):
                    resultado_final['estagios_bem_sucedidos'].append(i)
        
        self.melhor_resultado = resultado_final
        
        if self.debug:
            print(f"\n🎯 RESULTADO FINAL:")
            print(f"Chave: {'✅' if resultado_final['chave'] else '❌'} {resultado_final['chave'] or 'N/A'} (fonte: {resultado_final['fonte_chave'] or 'N/A'})")
            print(f"Valor: {'✅' if resultado_final['valor'] else '❌'} {resultado_final['valor'] or 'N/A'} (fonte: {resultado_final['fonte_valor'] or 'N/A'})")
            print(f"Data: {'✅' if resultado_final['data'] else '❌'} {resultado_final['data'] or 'N/A'} (fonte: {resultado_final['fonte_data'] or 'N/A'})")
            print(f"Score Total: {resultado_final['score_total']} pontos")
            print(f"Estágios bem-sucedidos: {resultado_final['estagios_bem_sucedidos']}")


def process_single_file(file_path, usuario_from_name, lote_from_name, sequencia_from_name=""):
    """
    Processa um único arquivo de imagem (nota fiscal) e extrai informações usando arquitetura de 7 estágios.
    
    Status possíveis:
    - chave_extraida_qr: Chave fiscal extraída com sucesso do QR Code
    - chave_extraida_ocr: Chave fiscal extraída com sucesso do texto OCR
    - dados_parciais_ocr: Alguns dados extraídos por OCR, mas sem chave fiscal
    - sem_dados_fiscais: Nenhum dado fiscal relevante encontrado
    """
    # Inicializa processador de 7 estágios - Debug controlado pela variável global
    processador = ProcessadorNFCe7Estagios(debug=DEBUG_HABILITADO)
    resultado_7_estagios = processador.processar_arquivo_7_estagios(file_path)
    
    # metadata
    stats = os.stat(file_path)
    hora_scan = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    
    resultado = {
        "id_tabela": None,
        "id_cupom": "",
        "chave": "",
        "data_emissao": "",
        "numero_cupom": "",
        "valor_nota": None,
        "mes_emissao": "",
        "ano_emissao": "",
        "numero_sat": "",
        "num_serie": "",
        "cnpj": "",
        "data_captura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": usuario_from_name,
        "status": "",
        "lote": lote_from_name,
        "sequencia": sequencia_from_name,
        "estagio": "",
        "hora_scan": hora_scan,
        "tipo": "",
        "pasta_filename": file_path
    }

    # Extrai dados do resultado dos 7 estágios
    if resultado_7_estagios['chave']:
        resultado["chave"] = resultado_7_estagios['chave']
        # Parse da chave para extrair metadados
        try:
            chave_info = parse_chave_65(resultado_7_estagios['chave'])
            if chave_info:
                resultado["cnpj"] = chave_info.get("cnpj", "")
                resultado["mes_emissao"] = chave_info.get("mes", "")
                resultado["ano_emissao"] = f"20{chave_info.get('ano_2', '')}"
                resultado["numero_cupom"] = chave_info.get("numero", "")
                resultado["num_serie"] = chave_info.get("serie", "")
                # Composição do IdCupom conforme regra CASE SQL
                chave = resultado_7_estagios['chave']
                novo_idcupom = ""
                if chave and len(chave) >= 44:
                    modelo = chave[20:22]
                    if modelo == "65":
                        # SUBSTRING(chave, 7, 14) + SUBSTRING(chave, 27, 8) + '20' + SUBSTRING(chave, 3, 2) + SUBSTRING(chave, 5, 2)
                        novo_idcupom = chave[6:20] + chave[26:34] + "20" + chave[2:4] + chave[4:6]
                    else:
                        # SUBSTRING(chave, 7, 14) + '00' + SUBSTRING(chave, 32, 6) + '20' + SUBSTRING(chave, 3, 2) + SUBSTRING(chave, 5, 2)
                        novo_idcupom = chave[6:20] + "00" + chave[31:37] + "20" + chave[2:4] + chave[4:6]
                resultado["id_cupom"] = novo_idcupom if novo_idcupom else chave[:50]
            else:
                resultado["id_cupom"] = resultado_7_estagios['chave'][:50]
        except:
            resultado["id_cupom"] = resultado_7_estagios['chave'][:50]
    
    if resultado_7_estagios['valor']:
        resultado["valor_nota"] = resultado_7_estagios['valor']
    
    if resultado_7_estagios['data']:
        resultado["data_emissao"] = resultado_7_estagios['data']
        # Extrai mês e ano da data se possível
        try:
            if "/" in resultado_7_estagios['data']:
                partes = resultado_7_estagios['data'].split("/")
                if len(partes) >= 3:
                    resultado["mes_emissao"] = partes[1]
                    resultado["ano_emissao"] = partes[2]
        except:
            pass

    # Define status baseado nos estágios bem-sucedidos
    estagios_sucesso = resultado_7_estagios.get('estagios_bem_sucedidos', [])
    fonte_chave = resultado_7_estagios.get('fonte_chave', '')
    
    if resultado_7_estagios['chave']:
        if fonte_chave == 'qr':
            resultado["status"] = "chave_extraida_qr"
            resultado["estagio"] = "1_qr_code"
        elif fonte_chave == 'ocr':
            resultado["status"] = "chave_extraida_ocr" 
            resultado["estagio"] = "3_ocr"
        else:
            resultado["status"] = "chave_extraida_validacao"
            resultado["estagio"] = "4_validacao"
    elif 3 in estagios_sucesso:  # OCR teve sucesso mas sem chave
        resultado["status"] = "dados_parciais_ocr"
        resultado["estagio"] = "3_ocr_parcial"
    else:
        resultado["status"] = "sem_dados_fiscais"
        resultado["estagio"] = "0_falha"

    # Adiciona metadados dos 7 estágios
    resultado["score_total"] = resultado_7_estagios.get('score_total', 0)
    resultado["estagios_sucesso"] = len(estagios_sucesso)
    resultado["fonte_dados"] = {
        'chave': resultado_7_estagios.get('fonte_chave'),
        'valor': resultado_7_estagios.get('fonte_valor'), 
        'data': resultado_7_estagios.get('fonte_data')
    }

    # Adiciona o log estruturado ao resultado
    resultado["log_arquivo"] = resultado_7_estagios.get('log_arquivo', {})

    print(f"✅ CONCLUÍDO: {resultado['status']} | Score: {resultado['score_total']} | Estágios: {estagios_sucesso}")
    
    return True, resultado


def processar_todas_pastas(base_path, processar_estagio2=True):
    """
    Processa todas as pastas de imagens encontradas no base_path
    Com LOG ESTRUTURADO por arquivo conforme solicitado
    """
    print("=" * 60)
    print("🚀 INICIO DO PROCESSAMENTO")
    print("=" * 60)
    
    resultados_finais = []
    log_completo = []  # Log estruturado de todos os arquivos
    pastas_encontradas = []

    # --- NOVO: Carrega lista de arquivos já processados, se houver CSV de progresso ---
    import glob
    import pandas as pd
    arquivos_processados = set()
    arquivos_csv = sorted(glob.glob(os.path.join(base_path, 'progresso_temp_*.csv')))
    if arquivos_csv:
        print(f"🔄 Encontrado(s) {len(arquivos_csv)} arquivo(s) de progresso. Usando o mais recente para pular arquivos já processados.")
        csv_mais_recente = arquivos_csv[-1]
        try:
            df_progresso = pd.read_csv(csv_mais_recente)
            col = None
            if 'pasta_filename' in df_progresso.columns:
                col = 'pasta_filename'
            elif 'arquivo' in df_progresso.columns:
                col = 'arquivo'
            if col:
                arquivos_processados = set(
                    str(x) for x in df_progresso[col].dropna().tolist()
                    if isinstance(x, str) or (isinstance(x, (int, float)) and not pd.isna(x))
                )
            print(f"🔄 {len(arquivos_processados)} arquivos já processados serão pulados.")
        except Exception as e:
            print(f"⚠️ Erro ao ler CSV de progresso: {e}")
    
    for pasta_data in os.listdir(base_path):
        pasta_completa = os.path.join(base_path, pasta_data)
        if not os.path.isdir(pasta_completa):
            continue
        pastas_encontradas.append(pasta_data)
    
    total_pastas = len(pastas_encontradas)
    print(f"📂 PASTA LIDA: {total_pastas} pastas encontradas")
    
    import time
    ultimo_salvamento = time.time()
    intervalo_salvamento = 300  # 5 minutos em segundos
    for i, pasta_data in enumerate(pastas_encontradas, 1):
        pasta_completa = os.path.join(base_path, pasta_data)
        print(f"\n📁 [{i}/{total_pastas}] Processando pasta: {pasta_data}")
        
        # Conta total de arquivos na pasta
        total_arquivos = 0
        arquivos_para_processar = []
        for raiz, _, arquivos in os.walk(pasta_completa):
            for arquivo in arquivos:
                if not arquivo.lower().endswith(".jpg"):
                    continue
                caminho = os.path.join(raiz, arquivo)
                arquivos_para_processar.append((caminho, arquivo))
                total_arquivos += 1
        
        print(f"📄 QTD ARQUIVO: {total_arquivos}")
        
        # Processa arquivo por arquivo
        contador_processados = 0
        resolvidos_pasta = 0
        
        for caminho, arquivo in arquivos_para_processar:
            # NOVO: Pula se já processado
            if caminho in arquivos_processados:
                print(f"⏩ Pulando já processado: {caminho}")
                continue
            contador_processados += 1
            # Extrai informações do arquivo
            partes = arquivo.rsplit(".", 1)[0].split("_")
            lote = partes[0] if len(partes) >= 1 else ""
            usuario = partes[1] if len(partes) >= 2 else ""
            sequencia = partes[2] if len(partes) >= 3 else ""

            # Salvamento automático a cada 5 minutos
            tempo_atual = time.time()
            if tempo_atual - ultimo_salvamento >= intervalo_salvamento and resultados_finais:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_csv = os.path.join(BASE_PATH, f"progresso_temp_{ts}.csv")
                try:
                    import pandas as pd
                    df_temp = pd.DataFrame(resultados_finais)
                    df_temp.to_csv(out_csv, index=False)
                    print(f"💾 Progresso salvo automaticamente em: {out_csv}")
                    ultimo_salvamento = tempo_atual
                except Exception as e:
                    print(f"⚠️ Erro ao salvar progresso automático: {e}")
            
            try:
                # Processa arquivo com 7 estágios
                sucesso_e1, info_e1 = process_single_file(caminho, usuario, lote, sequencia)

                # Extrai log do arquivo dos 7 estágios
                log_arquivo = info_e1.get('log_arquivo', {})
                if log_arquivo:
                    # Formata log conforme solicitado
                    log_linha = f"Arquivo {arquivo}|estágio 1 - {log_arquivo.get('estagio_1', 'null')}|estágio 2 - {log_arquivo.get('estagio_2', 'null')}|estágio 3 - {log_arquivo.get('estagio_3', 'null')}|estágio 4 - {log_arquivo.get('estagio_4', 'null')}|estágio 5 - {log_arquivo.get('estagio_5', 'null')}|estágio 6 - {log_arquivo.get('estagio_6', 'null')}|estágio 7 - {log_arquivo.get('estagio_7', 'null')}|Resultado={log_arquivo.get('resultado', 'não resolvido')}"
                    log_completo.append(log_linha)
                    print(log_linha)

                # Adiciona aos resultados
                resultados_finais.append(info_e1)

                # 🆕 CRITÉRIO CORRIGIDO: só conta como resolvido se tem CHAVE + VALOR + DATA
                tem_chave = bool(info_e1.get('id_cupom'))
                tem_valor = bool(info_e1.get('valor_nota'))
                tem_data = bool(info_e1.get('data_emissao'))

                if tem_chave and tem_valor and tem_data:
                    resolvidos_pasta += 1

            except Exception as e:
                # Log de erro
                log_linha = f"Arquivo {arquivo}|estágio 1 - erro|estágio 2 - null|estágio 3 - null|estágio 4 - null|estágio 5 - null|estágio 6 - null|estágio 7 - null|Resultado=erro ({str(e)[:30]}...)"
                log_completo.append(log_linha)
                print(log_linha)
                
                # Cria um registro de erro
                erro_info = {
                    "id_tabela": None, "id_cupom": "", "data_emissao": "", "numero_cupom": "",
                    "valor_nota": None, "mes_emissao": "", "ano_emissao": "", "numero_sat": "",
                    "num_serie": "", "cnpj": "", "valor_site_fazenda": "", "data_site_fazenda": "",
                    "status_site_fazenda": "", "cnpj_site_fazenda": "", "data_captura": "",
                    "usuario": usuario, "status": "erro", "estagio": "erro", "lote": lote,
                    "sequencia": sequencia, "hora_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "tipo": "jpg", "pasta_filename": caminho
                }
                resultados_finais.append(erro_info)
        
        print(f"  ✅ Pasta concluída: {resolvidos_pasta}/{total_arquivos} arquivos resolvidos")
    
    # RESUMO FINAL conforme solicitado
    print("\n" + "=" * 60)
    print("📊 RESUMO GERAL")
    print("=" * 60)

    if resultados_finais:
        # 🆕 RESUMO CORRIGIDO: conta como resolvido só se tem CHAVE + VALOR + DATA
        total_resolvidos = len([r for r in resultados_finais 
                               if r.get('id_cupom') and r.get('valor_nota') and r.get('data_emissao')])
        total_nao_resolvidos = len(resultados_finais) - total_resolvidos
        
        print(f"📈 Total processado: {len(resultados_finais)} arquivos")
        print(f"✅ Com valor: {total_resolvidos}")
        print(f"❌ Sem valor: {total_nao_resolvidos}")
        if len(resultados_finais) > 0:
            taxa = (total_resolvidos / len(resultados_finais)) * 100
            print(f"🎯 Taxa de sucesso: {taxa:.1f}%")


    # Gera DataFrame e salva Excel
    if not resultados_finais:
        print("⚠️  Nenhum resultado para salvar")
        return None
        
    df = pd.DataFrame(resultados_finais)
    # Renomeia colunas 'A' e 'B' se existirem
    # Define a ordem e nomes corretos das colunas para o Excel
    colunas = [
        "id_cupom", "chave", "data_emissao", "numero_cupom", "valor_nota",
        "mes_emissao", "ano_emissao", "numero_sat", "num_serie", "cnpj",
        "valor_site_fazenda", "data_site_fazenda", "status_site_fazenda", "cnpj_site_fazenda",
        "data_captura", "usuario", "status", "estagio", "lote", "sequencia", "hora_scan", "tipo", "pasta_filename"
    ]
    # Garante que todas as colunas existam
    for c in colunas:
        if c not in df.columns:
            df[c] = None
    df = df[colunas]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(BASE_PATH, OUTPUT_FILENAME.format(ts=ts))

    # Salva o Excel e gera log do resultado
    df.to_excel(out, index=False)

    # Log detalhado dos resultados - CORRIGIDO
    total_registros = len(df)
    registros_completos = len(df[(df['id_cupom'].notna() & (df['id_cupom'] != '')) & 
                                 (df['valor_nota'].notna() & (df['valor_nota'] != '')) &
                                 (df['data_emissao'].notna() & (df['data_emissao'] != ''))])
    registros_incompletos = total_registros - registros_completos

    print(f"\n📊 RELATÓRIO DE RESULTADOS:")
    print(f"📁 Arquivo salvo: {os.path.basename(out)}")
    print(f"📈 Total de registros: {total_registros}")
    print(f"✅ Com valor extraído: {registros_completos}")
    print(f"❌ Sem valor: {registros_incompletos}")
    if total_registros > 0:
        taxa_sucesso = (registros_completos / total_registros) * 100
        print(f"🎯 Taxa de sucesso: {taxa_sucesso:.1f}%")
    
    print(f"\n✅ PROCESSAMENTO CONCLUÍDO!")
    print(f"📊 Arquivo gerado: {os.path.basename(out)}")
    print(f"📍 Local: {out}")

    # Pergunta para importação após o processamento
    resposta = input("\nDeseja importar os dados para o banco local agora? (s/n): ").strip().lower()
    if resposta == 's':
        # Conexão com banco local (ajuste DSN, usuário e senha conforme necessário)
        # pandas já está importado globalmente
        from sqlalchemy import create_engine, text
        dsn_local = 'NFPSql'
        usuario_local = 'sa'
        senha_local = ''
        engine_local = create_engine(
            f'mssql+pyodbc://{usuario_local}:{senha_local}@{dsn_local}?driver=ODBC+Driver+17+for+SQL+Server'
        )
        # Lê o DataFrame gerado
        df_import = pd.read_excel(out, dtype=str).fillna("")
        total = len(df_import)
        inseridos = 0
        rejeitados = []
        erros_insercao = []
        duplicidades = []
        with engine_local.begin() as conn:
            for _, row in df_import.iterrows():
                def safe_int(val):
                    try:
                        return int(str(val).replace(".0", "").replace(",", "").strip())
                    except:
                        return None
                def safe_float(val):
                    try:
                        return float(str(val).replace(",", ".").replace("R$", "").strip())
                    except:
                        return None
                def safe_datetime(val):
                    try:
                        return pd.to_datetime(val, errors='coerce')
                    except:
                        return None
                reg = {
                    "IdCupom": str(row.get("id_cupom"))[:50] if row.get("id_cupom") else None,
                    "Lote": safe_int(row.get("lote")),
                    "DataCad": pd.Timestamp.now(),
                    "Chave": str(row.get("chave"))[:50] if row.get("chave") else None,
                    "ValorNF": safe_float(row.get("valor_nota")),
                    "Ano": safe_int(row.get("ano_emissao")),
                    "Mes": safe_int(row.get("mes_emissao")),
                    "CNPJ": str(row.get("cnpj"))[:20] if row.get("cnpj") else None,
                    "DataNF": safe_datetime(row.get("data_emissao")),
                    "NUmNF": safe_int(row.get("numero_cupom")),
                    "Sat": str(row.get("numero_sat"))[:20] if row.get("numero_sat") else None,
                    "UserCaptura": str(row.get("usuario"))[:50] if row.get("usuario") else None,
                    "DtCaptura": safe_datetime(row.get("data_captura")),
                    "tipo": (str(row.get("tipo"))[:20] if row.get("tipo") else "IA Interna")
                }
                # Validação de CNPJ do lote
                try:
                    consulta = text("""
                        SELECT lit.CNPJ
                        FROM Lotes_Itens lit
                        WHERE lit.IdLote = :lote
                    """)
                    lote_int = None
                    try:
                        lote_int = int(reg["Lote"])
                    except Exception:
                        lote_int = reg["Lote"]
                    result = conn.execute(consulta, {"lote": lote_int}).fetchone()
                    if result:
                        cnpj_lote_db = str(result[0])
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
                    conn.execute(comando, {**reg, "DataCad": pd.Timestamp.now()})
                    inseridos += 1
                except Exception as e:
                    erro_str = str(e).lower()
                    if "duplicate" in erro_str or "primary key" in erro_str or "unique" in erro_str:
                        duplicidades.append({"IdCupom": reg["IdCupom"], "erro": "duplicidade"})
                        print(f"   ⚠️ Duplicidade detectada IdCupom={reg['IdCupom']}")
                    else:
                        erros_insercao.append({"IdCupom": reg["IdCupom"], "erro": str(e)})
                        print(f"❌ Erro ao inserir registro: {reg['IdCupom']} - {e}")
        print(f"\n✅ Importação concluída! {inseridos}/{total} registros inseridos no banco.")
        print(f"❌ Rejeitados: {len(rejeitados)} | ⚠️ Duplicidades: {len(duplicidades)} | Outros erros: {len(erros_insercao)}")
    else:
        print("\nImportação para o banco não realizada.")

def processar_arquivo_especifico(file_path, debug_detalhado=True):
    """
    Processa um arquivo específico com debug detalhado para análise.
    Útil para testar e debugar arquivos problemáticos.
    """
    print(f"\n🔍 ANÁLISE DETALHADA DO ARQUIVO: {os.path.basename(file_path)}")
    print("=" * 60)
    
    # Extrai informações do nome do arquivo
    arquivo_nome = os.path.basename(file_path)
    partes = arquivo_nome.rsplit(".", 1)[0].split("_")
    lote = partes[0] if len(partes) >= 1 else ""
    usuario = partes[1] if len(partes) >= 2 else ""
    sequencia = partes[2] if len(partes) >= 3 else ""
    
    print(f"📋 Lote: {lote}, Usuário: {usuario}, Sequência: {sequencia}")
    
    try:
        # ESTÁGIO 1: QR Code
        print(f"\n🔍 ESTÁGIO 1: LEITURA DE QR CODE")
        qrs = read_qr_from_image(file_path)
        if qrs:
            print(f"✅ QR encontrado: {len(qrs)} códigos")
            for i, qr in enumerate(qrs):
                print(f"   QR {i+1}: {qr[:100]}..." if len(qr) > 100 else f"   QR {i+1}: {qr}")
        else:
            print(f"❌ Nenhum QR encontrado")
        
        # ESTÁGIO 2: TODO - Código de barras
        print(f"\n📊 ESTÁGIO 2: CÓDIGO DE BARRAS (TODO)")
        print(f"⏳ Implementação futura")
        
        # ESTÁGIO 3: OCR
        print(f"\n📝 ESTÁGIO 3: OCR DE TEXTO")
        texto_ocr = ocr_text_from_image(file_path)
        print(f"📄 Texto extraído: {len(texto_ocr)} caracteres")
        
        # Extrai campos do OCR
        campos_ocr = extrair_campos_de_texto(texto_ocr)
        print(f"🔍 Campos encontrados no OCR:")
        for campo, valor in campos_ocr.items():
            print(f"   {campo}: {valor}")
        
        # ESTÁGIO 4: Validação (se tem chave)
        chave_encontrada = None
        if qrs:
            # Busca chave no QR
            for q in qrs:
                parametro_qr = q
                if "?p=" in q:
                    parametro_qr = q.split("?p=")[1]
                
                if "|" in parametro_qr:
                    dados_qr = extrair_dados_qr_inteligente(parametro_qr)
                    if dados_qr.get("chave_44"):
                        chave_encontrada = dados_qr["chave_44"]
                        break
                
                import re
                m = re.search(r'3525(\d{44})', q)
                if m:
                    chave_encontrada = m.group(1)
                    break
        
        if not chave_encontrada and campos_ocr.get("chave_44"):
            chave_encontrada = campos_ocr["chave_44"]
        
        if chave_encontrada:
            print(f"\n🔐 ESTÁGIO 4: VALIDAÇÃO DA CHAVE")
            print(f"🔑 Chave encontrada: {chave_encontrada}")
            
            # Valida DV
            dv_valido = calcular_dv_chave(chave_encontrada)
            print(f"✅ DV válido: {dv_valido}")
            
            # Consulta site
            if qrs:
                print(f"🌐 Consultando site da Fazenda...")
                dados_site = consultar_nfce_fazenda_sp(qrs[0])
                if dados_site:
                    print(f"✅ Dados do site:")
                    for campo, valor in dados_site.items():
                        print(f"   {campo}: {valor}")
                else:
                    print(f"❌ Falha na consulta do site")
        else:
            print(f"\n❌ ESTÁGIO 4: Nenhuma chave encontrada para validação")
        
        # ANÁLISE FINAL
        print(f"\n📊 ANÁLISE FINAL:")
        print(f"QR: {'✅' if qrs else '❌'}")
        print(f"Chave: {'✅' if chave_encontrada else '❌'}")
        print(f"Valor OCR: {'✅' if campos_ocr.get('valor_nota') else '❌'} - {campos_ocr.get('valor_nota', 'N/A')}")
        print(f"Data OCR: {'✅' if campos_ocr.get('data_emissao') else '❌'} - {campos_ocr.get('data_emissao', 'N/A')}")
        
        return {
            'qrs': qrs,
            'chave': chave_encontrada,
            'campos_ocr': campos_ocr,
            'texto_ocr': texto_ocr
        }
        
    except Exception as e:
        print(f"❌ ERRO na análise: {e}")
        import traceback
        print(traceback.format_exc())
        return None

# === execução ===
if __name__ == "__main__":
    print("🚀 INICIANDO PROCESSAMENTO DE NOTAS FISCAIS")
    start = datetime.now()
    print(f"⏰ Início: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verifica se o Tesseract está funcionando
    if not verificar_tesseract():
        print("❌ Erro: Tesseract não está funcionando corretamente")
        print("   Verifique se o Tesseract está instalado e configurado")
        exit(1)
    
    pass
    
    try:
        out = processar_todas_pastas(BASE_PATH, processar_estagio2=True)
        dur = datetime.now() - start
        
        print(f"⏱️  Tempo total: {dur}")
        
    except Exception as e:
        print(f"❌ ERRO DURANTE O PROCESSAMENTO: {e}")
        import traceback
        print(f"🔍 Detalhes: {traceback.format_exc()}")
        raise
