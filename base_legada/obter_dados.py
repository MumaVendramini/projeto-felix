import os
import sys
import time
import json
import threading
from datetime import datetime
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import pyautogui

# Cole aqui a URL do Web App gerada no Google Apps Script da sua planilha
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhtGP5FSLktLAu-_EuZ3PjOeFnGNlIbflMH2ZvtSWHDPIeSJDJS2CM__H5ucN5Oj2U/exec"

# Nome do grupo do WhatsApp para onde enviar o print da planilha
WHATSAPP_GROUP_NAME = "Automatizações EcoExpo"

def main():
    # Garantir que o diretorio de trabalho seja a pasta do script (evita erro de permissao ao rodar via Agendador de Tarefas)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir:
        os.chdir(script_dir)
        
    print("=== INICIANDO AUTOMACAO NFP - CERTIFICADO DIGITAL ===")
    
    # Criar pasta para screenshots se nao existir
    os.makedirs("screenshots", exist_ok=True)
    
    # Configurar opcoes do Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # Pasta para salvar o perfil do Chrome (cookies, login do WhatsApp Web, etc.)
    profile_dir = os.path.join(script_dir, "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    # IMPORTANTE:
    # O Chrome precisa rodar em modo headful (com janela visivel) para exibir a caixa de selecao de certificados.
    
    print("Inicializando o navegador Chrome...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        url = "https://www.nfp.fazenda.sp.gov.br/login.aspx"
        print(f"Navegando para: {url}")
        driver.get(url)
        
        # Tirar screenshot inicial
        time.sleep(3)
        driver.save_screenshot("screenshots/1_pagina_inicial.png")
        
        # 1. Clicar em Contribuinte ICMS
        print("Clicando em 'Contribuinte ICMS'...")
        wait = WebDriverWait(driver, 15)
        btn_contribuinte = wait.until(EC.element_to_be_clickable((By.ID, "rdBtnContribuinte")))
        btn_contribuinte.click()
        
        # Esperar carregar os elementos dinamicos
        time.sleep(2)
        driver.save_screenshot("screenshots/2_perfil_contribuinte.png")
        
        # Funcao auxiliar executada em segundo plano para pressionar ENTER apos delay
        def pressionar_enter_background(delay):
            pyautogui.FAILSAFE = False
            print(f"[Thread] Aguardando {delay} segundos antes de iniciar o loop de ENTER...")
            time.sleep(delay)
            print("[Thread] Iniciando loop de pressionamento de ENTER para confirmar o certificado...")
            for i in range(15):  # tenta 15 vezes, uma a cada 2 segundos
                print(f"[Thread] Pressionando ENTER (tentativa {i+1}/15)...")
                pyautogui.press('enter')
                time.sleep(2)
            print("[Thread] Loop de ENTER finalizado!")

        # 2. Iniciar thread em segundo plano antes do clique bloqueante
        print("Iniciando a thread do PyAutoGUI em segundo plano...")
        thread_enter = threading.Thread(target=pressionar_enter_background, args=(5,), daemon=True)
        thread_enter.start()
        
        # 3. Clicar em Acesso via certificado digital (imgBtnAcessoCertCNPJ)
        # Observacao: Esta chamada .click() costuma bloquear a execucao do script ate que o certificado seja escolhido
        print("Clicando em 'Acesso via certificado digital'...")
        btn_cert = wait.until(EC.element_to_be_clickable((By.ID, "imgBtnAcessoCertCNPJ")))
        btn_cert.click()
        print("Retornou do clique no certificado!")
        
        # 4. Aguardar o login e redirecionamento
        print("Aguardando o redirecionamento pos-login (maximo 30 segundos)...")
        logado = False
        for attempt in range(30):
            time.sleep(1)
            current_url = driver.current_url.lower()
            if "login.aspx" not in current_url and "logincertificado" not in current_url:
                print(f"Login detectado! URL atual: {driver.current_url}")
                logado = True
                break
        
        if not logado:
            print("Aviso: Nao foi detectado redirecionamento automatico da URL de login ainda. Tentando mais alguns segundos...")
            time.sleep(5)
            
        driver.save_screenshot("screenshots/3_pos_login.png")
        
        # 5. Navegar no menu: Consultar -> entidades -> consulta de consumidores doadores
        print("Iniciando navegacao pelo menu...")
        
        # Aguardar container do menu principal
        menu_superior = wait.until(EC.presence_of_element_located((By.ID, "MenuSuperior")))
        
        # Localizar e interagir com "Consultar"
        print("Procurando 'Consultar' no menu...")
        consultar_elem = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='MenuSuperior']//a[contains(text(), 'Consultar') or contains(text(), 'consultar') or contains(text(), 'CONSULTAR')]")))
        
        # Hover e click
        actions = ActionChains(driver)
        actions.move_to_element(consultar_elem).perform()
        time.sleep(1)
        consultar_elem.click()
        time.sleep(1)
        driver.save_screenshot("screenshots/4_menu_consultar.png")
        
        # Localizar e interagir com "entidades" ou "Entidades"
        print("Procurando 'Entidades' no submenu...")
        entidades_elem = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Entidades') or contains(text(), 'entidades') or contains(text(), 'ENTIDADES')]")))
        actions.move_to_element(entidades_elem).perform()
        time.sleep(1)
        entidades_elem.click()
        time.sleep(1)
        driver.save_screenshot("screenshots/5_menu_entidades.png")
        
        # Localizar e clicar em "consulta de consumidores doadores"
        print("Procurando 'Consulta de Consumidores Doadores'...")
        doadores_elem = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Consumidores Doadores') or contains(text(), 'consumidores doadores') or contains(text(), 'Consulta de Consumidores Doadores')]")))
        doadores_elem.click()
        
        print("Navegacao concluida. Aguardando a tabela carregar...")
        time.sleep(5)
        driver.save_screenshot("screenshots/6_tabela_resultado.png")
        
        # 6. Localizar a linha nov/2026 e coletar o numero da primeira coluna
        rows = driver.find_elements(By.XPATH, "//tr")
        print(f"Total de {len(rows)} linhas na tabela identificadas.")
        
        target_months = ["nov/2026", "nov/26", "11/2026", "novembro/2026", "novembro/26", "nov/ 2026"]
        valor_encontrado = None
        
        for idx, row in enumerate(rows):
            cols = row.find_elements(By.TAG_NAME, "td")
            if not cols:
                continue
            
            col_texts = [col.text.strip() for col in cols]
            row_text_full = " | ".join(col_texts)
            
            # Verificar se algum dos meses alvo esta em alguma coluna
            for month in target_months:
                found_month = False
                for text in col_texts:
                    if month in text.lower():
                        found_month = True
                        break
                if found_month:
                    print(f"Linha correspondente encontrada: '{row_text_full}'")
                    # Coletar todas as colunas da linha
                    row_data = {
                        "mes": col_texts[0] if len(col_texts) > 0 else "",
                        "doador_pleno": col_texts[1] if len(col_texts) > 1 else "",
                        "doador_restrito": col_texts[2] if len(col_texts) > 2 else "",
                        "total_doadores": col_texts[3] if len(col_texts) > 3 else ""
                    }
                    valor_encontrado = row_data
                    break
            if valor_encontrado:
                break
                
        # Helper to clean numbers formatted in PT-BR (e.g. "3.588" -> 3588)
        def limpar_numero(texto):
            if not texto:
                return 0
            clean = "".join([c for c in texto if c.isdigit()])
            return int(clean) if clean else 0

        if valor_encontrado:
            print(f"\nSUCESSO: Dados coletados para {valor_encontrado['mes']}:")
            print(f"  - Doador Pleno (1a coluna numerica): {valor_encontrado['doador_pleno']}")
            print(f"  - Doador Restrito (2a coluna numerica): {valor_encontrado['doador_restrito']}")
            print(f"  - Total Doadores: {valor_encontrado['total_doadores']}")
            
            # 1. Salvar em arquivo txt
            with open("resultado_consulta.txt", "w", encoding="utf-8") as f:
                f.write(f"Periodo: {valor_encontrado['mes']}\n")
                f.write(f"Doador Pleno (1a coluna de valor): {valor_encontrado['doador_pleno']}\n")
                f.write(f"Doador Restrito (2a coluna de valor): {valor_encontrado['doador_restrito']}\n")
                f.write(f"Total Doadores: {valor_encontrado['total_doadores']}\n")
                f.write(f"Data da Consulta: {time.strftime('%d/%m/%Y %H:%M:%S')}\n")
            
            # 2. Salvar / Acrescentar na planilha Excel
            excel_file = "historico_doadores.xlsx"
            new_row = {
                "Data da Consulta": [datetime.now().strftime("%d/%m/%Y %H:%M:%S")],
                "Periodo Alvo": [valor_encontrado["mes"]],
                "Doador Pleno": [limpar_numero(valor_encontrado["doador_pleno"])],
                "Doador Restrito": [limpar_numero(valor_encontrado["doador_restrito"])],
                "Total Doadores": [limpar_numero(valor_encontrado["total_doadores"])]
            }
            df_new = pd.DataFrame(new_row)
            
            if os.path.exists(excel_file):
                try:
                    df_old = pd.read_excel(excel_file)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True)
                    df_combined.to_excel(excel_file, index=False)
                    print(f"[OK] Excel atualizado: '{excel_file}' (nova linha adicionada)")
                except Exception as ex_excel:
                    print(f"[AVISO] Erro ao atualizar planilha Excel: {ex_excel}")
            else:
                try:
                    df_new.to_excel(excel_file, index=False)
                    print(f"[OK] Planilha Excel criada com sucesso: '{excel_file}'")
                except Exception as ex_excel:
                    print(f"[AVISO] Erro ao criar planilha Excel: {ex_excel}")
            
            # 3. Enviar para a planilha do Google Sheets (se configurado)
            if GOOGLE_SHEETS_WEBAPP_URL and GOOGLE_SHEETS_WEBAPP_URL != "SUA_URL_AQUI":
                print("Enviando dados para o Google Sheets online...")
                now = datetime.now()
                data_formatada = now.strftime("%d/%m/%Y %H:%M:%S")
                
                payload = {
                    "periodo": data_formatada,
                    "doador_pleno": limpar_numero(valor_encontrado["doador_pleno"]),
                    "doador_restrito": limpar_numero(valor_encontrado["doador_restrito"]),
                    "total_doadores": limpar_numero(valor_encontrado["total_doadores"])
                }
                
                try:
                    response = requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=payload, timeout=15)
                    if response.status_code == 200:
                        res_json = response.json()
                        if res_json.get("status") == "success":
                            print("[OK] Google Sheets atualizado com sucesso!")
                        else:
                            print(f"[AVISO] Erro no Apps Script: {res_json.get('message')}")
                    else:
                        print(f"[AVISO] Falha ao conectar ao Google Sheets. Status Code: {response.status_code}")
                except Exception as ex_sheets:
                    print(f"[AVISO] Erro ao enviar requisicao ao Google Sheets: {ex_sheets}")
            else:
                print("[INFO] Google Sheets nao configurado (URL vazia ou padrao). Pulei esta etapa.")
                
            # 4. Enviar print para o WhatsApp
            if WHATSAPP_GROUP_NAME and WHATSAPP_GROUP_NAME != "NOME_DO_GRUPO_DO_WHATSAPP":
                try:
                    enviar_print_whatsapp(driver, WHATSAPP_GROUP_NAME)
                except Exception as ex_wa:
                    print(f"[ERRO] Falha ao enviar print para o WhatsApp: {ex_wa}")
        else:
            print("[ERRO] Linha de nov/2026 nao foi encontrada na tabela.")
            
    except Exception as e:
        print(f"[ERRO] Ocorreu um erro na automacao: {e}")
        try:
            driver.save_screenshot("screenshots/erro_detalhado.png")
            print("Screenshot de erro salva em 'screenshots/erro_detalhado.png'")
        except:
            pass
    finally:
        print("Finalizando o navegador em 5 segundos...")
        time.sleep(5)
        driver.quit()

def enviar_print_whatsapp(driver, group_name):
    print("\nNavegando para a planilha do Google Sheets para tirar o print...")
    
    # 1. Configurar URL e tamanho da janela
    # Usando ?rm=minimal para ocultar menus e barras e ficar limpo
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1tiYNObBrhTMfGS4KYKQ831Zy7zD8xMnqNCCr6FY4jls/edit?rm=minimal"
    driver.set_window_size(1150, 750)
    driver.get(spreadsheet_url)
    
    print("Aguardando 7 segundos para a planilha renderizar...")
    time.sleep(7)
    
    # 2. Salvar screenshot da planilha
    image_path = "tabela_atualizada.png"
    driver.save_screenshot(image_path)
    print(f"Print da planilha salvo em: {image_path}")
    
    # 3. Navegar para o WhatsApp Web
    print("Navegando para o WhatsApp Web...")
    driver.get("https://web.whatsapp.com")
    
    wait = WebDriverWait(driver, 20)
    
    # 4. Aguardar login (verifica a presenca da barra lateral de conversas)
    print("=============================================================")
    print("AGUARDANDO LOGIN NO WHATSAPP WEB...")
    print("Se for a primeira vez, escaneie o QR Code na tela do navegador Chrome.")
    print("Nas proximas vezes o login sera feito automaticamente.")
    print("=============================================================")
    
    logged_in = False
    for i in range(120):  # Esperar ate 120 segundos pelo login
        try:
            driver.find_element(By.XPATH, "//div[@id='side']")
            logged_in = True
            break
        except:
            pass
        time.sleep(1)
        
    if not logged_in:
        print("[ERRO] Tempo limite de login esgotado no WhatsApp Web.")
        return False
        
    print("WhatsApp Web conectado com sucesso!")
    time.sleep(3)
    
    # 5. Localizar a caixa de pesquisa
    search_box = None
    search_input_xpaths = [
        "//div[@id='side']//p[@contenteditable='true']",
        "//div[@id='side']//div[@contenteditable='true']",
        "//div[@id='side']//*[@role='textbox']",
        "//div[@id='side']//input",
        "//p[@contenteditable='true']",
        "//div[@contenteditable='true'][@data-tab='3']"
    ]
    
    for xpath in search_input_xpaths:
        try:
            search_box = driver.find_element(By.XPATH, xpath)
            print(f"Caixa de pesquisa localizada via XPath: {xpath}")
            break
        except:
            pass
            
    if not search_box:
        print("[ERRO] Nao foi possivel localizar a caixa de pesquisa do WhatsApp Web.")
        return False
        
    print("Caixa de pesquisa pronta!")
    time.sleep(1)
    
    # 5. Pesquisar o grupo
    print(f"Pesquisando pelo grupo '{group_name}'...")
    search_box.click()
    try:
        # Limpar usando JS para garantir compatibilidade com contenteditable
        driver.execute_script("arguments[0].innerText = '';", search_box)
    except Exception as ex_clear:
        try:
            search_box.clear()
        except:
            pass
    time.sleep(1)
    search_box.send_keys(group_name)
    time.sleep(3)
    
    # 6. Clicar no grupo nos resultados da pesquisa
    group_xpaths = [
        f"//span[@title='{group_name}']",
        f"//*[@title='{group_name}']",
        f"//span[text()='{group_name}']",
        f"//*[text()='{group_name}']"
    ]
    
    group_clicked = False
    print("Selecionando o grupo nos resultados...")
    for xpath in group_xpaths:
        try:
            # Usar click nativo do Selenium para disparar corretamente o event handler do React!
            group_elem = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            group_elem.click()
            print(f"Grupo '{group_name}' selecionado com sucesso via XPath: {xpath}")
            group_clicked = True
            break
        except:
            pass
            
    if not group_clicked:
        try:
            search_box.send_keys(Keys.ENTER)
            print("Pressionado ENTER na barra de pesquisa como plano B.")
            group_clicked = True
        except Exception as e2:
            print(f"Falha ao tentar dar ENTER na barra de pesquisa: {e2}")
            
    if not group_clicked:
        print("[ERRO] Nao foi possivel entrar no grupo do WhatsApp.")
        return False
        
    time.sleep(3)
    
    # 7. Localizar input de arquivo e enviar o print
    print("Localizando o campo de upload de arquivo...")
    abs_path = os.path.abspath(image_path)
    
    # 7.1 Abrir o menu de anexo (+)
    try:
        clip_xpaths = [
            "//div[@id='main']//*[@data-testid='clip']",
            "//div[@id='main']//*[@aria-label='Anexar']",
            "//div[@id='main']//*[@aria-label='Attach']",
            "//div[@id='main']//span[@data-icon='plus']",
            "//div[@id='main']//div[@role='button']//span[@data-icon='plus']"
        ]
        for xpath in clip_xpaths:
            try:
                clip_btn = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].click();", clip_btn) # Clique JS para evitar bloqueio visual
                print("Botao de anexo (+) clicado.")
                break
            except:
                pass
    except Exception as e_clip:
        print(f"Aviso ao tentar clicar no botao de anexo: {e_clip}")
        
    time.sleep(2) # Aguarda o menu abrir e renderizar os inputs
    
    # 7.2 Clicar na opcao visual "Fotos e vídeos" para ativar o modo de envio correto no React
    menu_item_clicked = False
    menu_item_xpaths = [
        "//li[@data-testid='attach-image']",
        "//*[@data-testid='attach-image']",
        "//*[@data-testid='attach-menu-image']",
        "//span[contains(text(), 'Fotos') or contains(text(), 'fotos') or contains(text(), 'Photos')]/ancestor::li",
        "//div[contains(text(), 'Fotos') or contains(text(), 'fotos') or contains(text(), 'Photos')]/ancestor::div[@role='button']",
        "//*[contains(text(), 'Fotos e vídeos') or contains(text(), 'Photos & videos')]"
    ]
    
    for xpath in menu_item_xpaths:
        try:
            elem = driver.find_element(By.XPATH, xpath)
            driver.execute_script("arguments[0].click();", elem)
            print(f"Opcao 'Fotos e videos' clicada via XPath: {xpath}")
            menu_item_clicked = True
            break
        except:
            pass
            
    time.sleep(2) # Aguarda o input ser montado/reativado após o clique
    
    # Imprimir os inputs disponiveis para diagnostico no terminal
    try:
        all_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        print(f"DEBUG: Encontrados {len(all_inputs)} inputs de arquivo apos o clique:")
        for idx, inp in enumerate(all_inputs):
            print(f"  [{idx}] accept='{inp.get_attribute('accept')}'")
    except Exception as ex_dbg:
        print(f"Erro no print de debug: {ex_dbg}")

    file_uploaded = False
    
    # 7.3 Tenta fazer o upload enviando o arquivo para os inputs encontrados
    try:
        all_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        if len(all_inputs) > 0:
            target_input = all_inputs[0]
            # Procura por um input que aceite video ou o primeiro que aceita imagem ampla
            for inp in all_inputs:
                accept_attr = inp.get_attribute("accept") or ""
                if "video" in accept_attr:
                    target_input = inp
                    break
            
            target_input.send_keys(abs_path)
            print("Caminho do print enviado ao input de fotos selecionado.")
            file_uploaded = True
    except Exception as ex_upload:
        print(f"Erro ao tentar fazer upload via lista de inputs: {ex_upload}")
        
    if not file_uploaded:
        # Ultimo plano B: tenta pelo input generico se a lista direta falhar
        try:
            file_input = driver.find_element(By.XPATH, "//input[@type='file']")
            file_input.send_keys(abs_path)
            print("Caminho do print enviado ao input generico (Plano B).")
            file_uploaded = True
        except Exception as ex_pb:
            print(f"Falha no plano B: {ex_pb}")
            
    if not file_uploaded:
        print("[ERRO] Nao foi possivel fazer o upload da imagem no WhatsApp Web.")
        return False
        
    time.sleep(4)
    
    # 8. Clicar no botao de enviar no preview
    print("Enviando o print...")
    send_xpath = "//span[@data-icon='send'] | //*[@aria-label='Enviar'] | //*[@aria-label='Send'] | //div[@role='button']//span[@data-icon='send']"
    send_clicked = False
    
    try:
        # Tenta esperar ate 8 segundos para o preview abrir e o botao de enviar aparecer
        wait_send = WebDriverWait(driver, 8)
        send_btn = wait_send.until(EC.element_to_be_clickable((By.XPATH, send_xpath)))
        driver.execute_script("arguments[0].click();", send_btn)
        print("Botao de enviar clicado com sucesso!")
        send_clicked = True
    except Exception as e_send:
        print(f"Botao de enviar nao localizado ou nao clicado: {e_send}. Tentando pressionar ENTER...")
        try:
            actions = ActionChains(driver)
            actions.send_keys(Keys.ENTER).perform()
            print("Enviado pressionando ENTER no teclado.")
            send_clicked = True
        except Exception as ex_enter:
            print(f"Falha ao tentar enviar por ENTER: {ex_enter}")
            
    if send_clicked:
        print("Aguardando 7 segundos para o WhatsApp finalizar o envio...")
        time.sleep(7)
        print("Envio concluido com sucesso!")
        return True
    else:
        print("[ERRO] Nao foi possivel enviar o print no preview.")
        return False

if __name__ == "__main__":
    main()
