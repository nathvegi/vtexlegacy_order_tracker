# --- Importações de Bibliotecas ---
import os
import re
import threading
import time
from datetime import datetime
import json  # Importar o módulo json
import requests
import customtkinter as ctk
from tkinter import TclError
from dotenv import load_dotenv

# --- Configurações Iniciais ---
load_dotenv()

VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT')
APP_KEY = os.getenv('VTEX_APP_KEY')
APP_TOKEN = os.getenv('VTEX_APP_TOKEN')

# Verifica se as variáveis de ambiente foram carregadas
if not all([VTEX_ACCOUNT, VTEX_ENVIRONMENT, APP_KEY, APP_TOKEN]):
    VTEX_CONFIG_ERROR = "ERRO CRÍTICO: Variáveis de ambiente VTEX não foram carregadas. Verifique seu arquivo .env."
else:
    VTEX_CONFIG_ERROR = None

# Configurações de Headers e Environment VTEX
HEADERS = {
    'Content-Type': 'application/json',
    'X-VTEX-API-AppKey': APP_KEY,
    'X-VTEX-API-AppToken': APP_TOKEN
}

BASE_URL = f'https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br'

# Variáveis globais
monitoring_active = False
app = None # Definir 'app' como None globalmente e manter assim.

TARGET_SALES_CHANNEL = os.getenv('VTEX_TARGET_SALES_CHANNEL', '1') # Define a política comercial dos pedidos consultados.
SLEEP_TIME_SECONDS = int(os.getenv('VTEX_SLEEP_TIME_SECONDS', 1800)) # Define o tempo de frequência do polling (intervalo de consulta) em segundos.

# --- Funções para carregar e processar pedidos processados ---
def carregar_pedidos_processados(): # Única estratégia possível para evitar salvar o mesmo pedido mais de 1x no master data v1 
    try:
        if os.path.exists('pedidos_processados.txt'):
            with open('pedidos_processados.txt', 'r') as f:
                return set(json.load(f))
        return set()
    except json.JSONDecodeError:
        log_message("[ERRO] Arquivo 'pedidos_processados.txt' está corrompido ou vazio. Criando um novo set vazio.", "ERROR")
        return set()
    except Exception as e:
        log_message(f"[ERRO] Falha ao carregar pedidos processados: {e}", "ERROR")
        return set()

def salvar_pedidos_processados(processed_orders):
    try:
        with open('pedidos_processados.txt', 'w') as f:
            json.dump(list(processed_orders), f) # Converte set para list para serialização JSON
        log_message("Pedidos processados salvos.", "DEBUG")
    except Exception as e:
        log_message(f"[ERRO] Falha ao salvar pedidos processados: {e}", "ERROR")

# Inicializa pedidos_processados.txt ao iniciar o programa, carregando do arquivo
pedidos_processados = carregar_pedidos_processados()

# --- Configurações do CustomTkinter (Aparência da interface) ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# --- Funções de Logging para a GUI ---
def log_message(message, level="INFO"):
    """Função para adicionar mensagens ao log da GUI."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] [{level}] {message}\n"
    try:
        if app: # Verifica se 'app' foi definido (instância da GUI)
            app.after(0, lambda: _insert_log_message_into_gui(full_message))
        else:
            print(full_message.strip()) # Se 'app' não existe (GUI ainda não iniciou), imprime no console
    except Exception as e:
        print(f"Erro ao logar na GUI: {e} - Mensagem original: {full_message.strip()}")

def _insert_log_message_into_gui(full_message):
    """Função auxiliar para inserir a mensagem no log da GUI (chamada pela thread principal)."""
    # Esta função é sempre chamada via app.after, então 'app' já deve estar definido aqui.
    app.log_area.configure(state='normal')
    app.log_area.insert(ctk.END, full_message)
    app.log_area.see(ctk.END)
    app.log_area.configure(state='disabled')


# --- Funções da API VTEX ---
def consultar_pedidos_resumo(status='ready-for-handling', page=1):
    url = f'{BASE_URL}/api/oms/pvt/orders'
    params = {
        'f_status': status,
        'page': page,
        'per_page': 25 # Define o número de pedidos consultado por página.
    }
    log_message(f"[API] Consultando resumo de pedidos com status '{status}' na página {page}...", "DEBUG")
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        full_response_json = response.json()
        orders_list = full_response_json.get('list', [])
        return orders_list
    except requests.exceptions.HTTPError as e:
        log_message(f"[ERRO API] HTTP ao consultar resumo de pedidos: {e.response.status_code} - {e.response.text}", "ERROR")
        return []
    except requests.exceptions.RequestException as e:
        log_message(f"[ERRO API] Conexão ao consultar resumo de pedidos: {e}", "ERROR")
        return []

def consultar_detalhe_pedido(order_id):
    url = f'{BASE_URL}/api/oms/pvt/orders/{order_id}'
    log_message(f"[API] Consultando detalhes do pedido: {order_id}...", "DEBUG")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        log_message(f"[ERRO API] HTTP ao consultar detalhe do pedido {order_id}: {e.response.status_code} - {e.response.text}", "ERROR")
        return None
    except requests.exceptions.RequestException as e:
        log_message(f"[ERRO API] Conexão ao consultar detalhe do pedido {order_id}: {e}", "ERROR")
        return None

def gravar_no_masterdata(order_completo):
    order_id = order_completo.get('orderId')
    client_profile_data = order_completo.get('clientProfileData', {})

    body = {
        "orderId": order_id,
        "status": order_completo.get('status'),
        "creationDate": order_completo.get('creationDate'),
        "totalValue": order_completo.get('value', 0) / 100,
        "clientEmail": client_profile_data.get('email', ''),
        "clientPhoneCell": client_profile_data.get('phone', ''),
        "clientName": client_profile_data.get('firstName', '') + ' ' + client_profile_data.get('lastName', '')
    }

    create_url = f'{BASE_URL}/api/dataentities/OE/documents'

    log_message(f"[MD] Tentando criar novo documento para Order ID: {order_id}...", "INFO")

    try:
        response = requests.post(create_url, headers=HEADERS, json=body, timeout=30)

        if response.status_code == 201: # 201 Created - Sucesso na criação
            log_message(f"[MD] Evento criado com sucesso para pedido: {order_id}", "INFO")
            return True
        else: # Qualquer outro status é um erro na criação
            log_message(f"[ERRO MD] Falha ao criar pedido {order_id}: {response.status_code} - {response.text}", "ERROR")
            log_message(f"[ERRO MD] Response body: {response.text}", "ERROR")
            return False

    except requests.exceptions.HTTPError as e:
        log_message(f"[ERRO MD] HTTP ao criar para pedido {order_id}: {e.response.status_code} - {e.response.text}", "ERROR")
        log_message(f"[ERRO MD] Response body: {e.response.text}", "ERROR")
        return False
    except requests.exceptions.RequestException as e:
        log_message(f"[ERRO MD] Conexão ao criar para pedido {order_id}: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"[ERRO INESPERADO MD] ao criar para pedido {order_id}: {e}", "CRITICAL")
        return False

# --- Função Principal de Monitoramento (roda em uma thread separada) ---
def monitorar_pedidos_thread():
    global monitoring_active, pedidos_processados, app

    if VTEX_CONFIG_ERROR:
        log_message(VTEX_CONFIG_ERROR, "CRITICAL")
        if app: # Verificação para evitar erro se 'app' ainda não foi criado
            app.set_status("ERRO DE CONFIGURAÇÃO")
        return

    while monitoring_active:
        pedidos_resumo = [] # Inicializa pedidos_resumo como lista vazia a cada rodada
        try:
            log_message(f"[MONITOR] Iniciando nova rodada de monitoramento. Próxima checagem em {SLEEP_TIME_SECONDS // 60} minutos.", "INFO")
            log_message(f"[MONITOR] {len(pedidos_processados)} pedidos já processados (nesta ou sessões anteriores persistidas).", "INFO")

            pedidos_resumo = consultar_pedidos_resumo() # Aqui a variável é populada

            if pedidos_resumo:
                log_message(f"[MONITOR] Encontrados {len(pedidos_resumo)} pedidos resumidos.", "INFO")
                for pedido_resumido in pedidos_resumo:
                    if not monitoring_active:
                        log_message("[MONITOR] Monitoramento interrompido. Saindo da checagem atual.", "WARNING")
                        break

                    order_id = pedido_resumido.get('orderId')
                    
                    if order_id and order_id not in pedidos_processados:
                        log_message(f"\n[PROCESSANDO] --- Novo pedido: {order_id} ---", "INFO")
                        
                        pedido_completo = consultar_detalhe_pedido(order_id)
                        
                        if pedido_completo:
                            pedido_sales_channel = pedido_completo.get('salesChannel')
                            
                            if str(pedido_sales_channel) == TARGET_SALES_CHANNEL:
                                log_message(f"[FILTRO] Pedido {order_id} (Sales Channel: {pedido_sales_channel}) corresponde ao canal alvo '{TARGET_SALES_CHANNEL}'.", "INFO")
                                try:
                                    if gravar_no_masterdata(pedido_completo):
                                        pedidos_processados.add(order_id)
                                        if app: # Verificação para evitar erro se 'app' ainda não foi criado
                                            app.after(0, lambda: app.update_processed_count(len(pedidos_processados)))
                                        log_message(f"[PROCESSADO] Pedido {order_id} gravado no Master Data e adicionado ao set de processados.", "INFO")
                                    else:
                                        log_message(f"[PROCESSANDO] Falha CRÍTICA ao gravar pedido {order_id} no Master Data. NÃO adicionando a pedidos_processados para RE-TENTAR.", "ERROR")
                                except KeyError as ke:
                                    log_message(f"[ERRO CRÍTICO] Chave '{ke}' ausente no pedido {order_id}. Conteúdo do pedido COMPLETO: {pedido_completo}", "ERROR")
                                    pedidos_processados.add(order_id)
                                    log_message(f"[PROCESSADO] Pedido {order_id} marcado como processado devido a erro crítico para evitar novas tentativas nesta sessão.", "ERROR")
                                except Exception as e:
                                    log_message(f"[ERRO INESPERADO] ao processar pedido {order_id}: {e}. Conteúdo do pedido COMPLETO: {pedido_completo}", "ERROR")
                                    pedidos_processados.add(order_id)
                                    log_message(f"[PROCESSADO] Pedido {order_id} marcado como processado devido a erro inesperado para evitar novas tentativas nesta sessão.", "ERROR")
                            else:
                                log_message(f"[FILTRO] Pedido {order_id} (Sales Channel: {pedido_sales_channel}) não pertence ao Sales Channel '{TARGET_SALES_CHANNEL}'. Pulando.", "INFO")
                                pedidos_processados.add(order_id)
                        else:
                            log_message(f"[PROCESSANDO] Não foi possível obter os detalhes completos do pedido {order_id}. Pulando.", "WARNING")
                            pedidos_processados.add(order_id)
                    elif order_id:
                        log_message(f"[PROCESSANDO] Pedido {order_id} já processado anteriormente. Pulando.", "DEBUG")
                    else:
                        log_message(f"[AVISO] Pedido encontrado sem 'orderId' no resumo. Conteúdo: {pedido_resumido}", "WARNING")
            else:
                log_message("[MONITOR] Nenhum pedido resumido encontrado ou erro na consulta.", "WARNING")

            if monitoring_active:
                salvar_pedidos_processados(pedidos_processados)
                log_message(f"[MONITOR] Checagem concluída. Aguardando {SLEEP_TIME_SECONDS // 60} minutos para a próxima.", "INFO")
                time.sleep(SLEEP_TIME_SECONDS)

        except requests.exceptions.HTTPError as e:
            log_message(f"[ERRO API] HTTP ao consultar pedidos: {e.response.status_code} - {e.response.text}", "ERROR")
            salvar_pedidos_processados(pedidos_processados)
            time.sleep(60)
        except requests.exceptions.RequestException as e:
            log_message(f"[ERRO API] Erro de conexão ao consultar pedidos: {e}", "ERROR")
            salvar_pedidos_processados(pedidos_processados)
            time.sleep(60)
        except Exception as e:
            log_message(f"[ERRO CRÍTICO] Falha inesperada no monitoramento: {e}", "CRITICAL")
            salvar_pedidos_processados(pedidos_processados)
            time.sleep(60)
    
    salvar_pedidos_processados(pedidos_processados)
    if app: # Verificação para evitar erro se 'app' ainda não foi criado
        app.set_status("INATIVO")
    log_message("[MONITOR] Monitoramento parado.", "INFO")


# --- Classe da Interface Gráfica (CustomTkinter) ---
class Application(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VTEX Legacy Order Tracker - Monitoramento e Notificação de Pedidos - v4.5")
        self.geometry("800x600")

        try:
            self.iconbitmap('icon.ico')
        except TclError: # Usa tk.TclError importado
            print("AVISO: Não foi possível carregar o ícone da janela. Verifique o caminho e o formato (deve ser .ico).")

        self.monitoring_thread = None

        self.create_widgets()
        self.set_status("INATIVO")
        self.update_processed_count(len(pedidos_processados)) # Atualiza a contagem inicial ao carregar

        if VTEX_CONFIG_ERROR:
            ctk.CTkMessageBox.showerror("Erro de Configuração", VTEX_CONFIG_ERROR)
            self.start_button.configure(state=ctk.DISABLED)

    def create_widgets(self):
        status_frame = ctk.CTkFrame(self)
        status_frame.pack(pady=10, fill=ctk.X, padx=10)

        ctk.CTkLabel(status_frame, text="Status do Monitor:").pack(side=ctk.LEFT, padx=(10,0))
        self.status_label = ctk.CTkLabel(status_frame, text="INATIVO", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_label.pack(side=ctk.LEFT, padx=5)

        ctk.CTkLabel(status_frame, text="Pedidos Processados na Sessão:").pack(side=ctk.LEFT, padx=(20, 0))
        self.processed_count_label = ctk.CTkLabel(status_frame, text="0", font=ctk.CTkFont(size=12, weight="bold"))
        self.processed_count_label.pack(side=ctk.LEFT, padx=5)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)

        self.start_button = ctk.CTkButton(button_frame, text="Iniciar Monitoramento", command=self.start_monitoring, width=200, height=40)
        self.start_button.pack(side=ctk.LEFT, padx=10)

        self.stop_button = ctk.CTkButton(button_frame, text="Parar Monitoramento", command=self.stop_monitoring, width=200, height=40, state=ctk.DISABLED)
        self.stop_button.pack(side=ctk.LEFT, padx=10)

        ctk.CTkLabel(self, text="Logs do Sistema:").pack(anchor=ctk.W, padx=10, pady=(0, 5))
        self.log_area = ctk.CTkTextbox(self, wrap="word", state='disabled', width=780, height=300)
        self.log_area.pack(padx=10, pady=10, fill=ctk.BOTH, expand=True)

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(pady=5)
        ctk.CTkLabel(info_frame, text=f"Intervalo de Verificação: {SLEEP_TIME_SECONDS // 60} minutos | Política Comercial: {TARGET_SALES_CHANNEL} (Main)").pack()
        ctk.CTkLabel(info_frame, text="Feche esta janela para encerrar o programa.").pack()

    def set_status(self, status):
        self.status_label.configure(text=f"{status}")
        if status == "ATIVO":
            self.status_label.configure(text_color="green")
        elif status == "INATIVO":
            self.status_label.configure(text_color="red")
        elif "ERRO" in status or "CRITICAL" in status:
            self.status_label.configure(text_color="orange")

    def update_processed_count(self, count):
        self.processed_count_label.configure(text=str(count))

    def start_monitoring(self):
        global monitoring_active
        if not monitoring_active:
            monitoring_active = True
            self.start_button.configure(state=ctk.DISABLED)
            self.stop_button.configure(state=ctk.NORMAL)
            self.log_area.configure(state='normal')
            self.log_area.delete(1.0, ctk.END)
            self.log_area.configure(state='disabled')

            self.set_status("ATIVO")

            log_message("Monitoramento iniciado. Verifique os logs abaixo.", "INFO")
            
            self.monitoring_thread = threading.Thread(target=monitorar_pedidos_thread, daemon=True)
            self.monitoring_thread.start()
        else:
            log_message("Monitoramento já está ativo.", "WARNING")

    def stop_monitoring(self):
        global monitoring_active
        if monitoring_active:
            monitoring_active = False
            self.start_button.configure(state=ctk.NORMAL)
            self.stop_button.configure(state=ctk.DISABLED)
            self.set_status("INATIVO") 
            log_message("Monitoramento sendo finalizado. Aguarde.", "WARNING")
        else:
            log_message("Monitoramento já está inativo.", "WARNING")

# --- Execução Principal da GUI ---
if __name__ == '__main__':
    app = Application() 
    app.mainloop()