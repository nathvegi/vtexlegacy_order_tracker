## 🛍️ VTEX Legacy Order Tracker - Monitoramento e Notificação de Pedidos

![image](https://github.com/user-attachments/assets/178b9af7-2ccc-45bc-bbcb-e7e01f0327a1)

---

### 🚀 Visão Geral

Este projeto oferece uma solução simples e de baixo custo para superar uma das principais limitações das lojas VTEX em Legacy: a ausência de um mecanismo nativo para lidar com eventos de pedidos, como EventBridge, apps dedicados ou webhooks configuráveis diretamente na plataforma.

Na VTEX Legacy, a única forma nativa de integração com eventos de pedidos é por meio de consultas periódicas (API Polling). Este aplicativo atua exatamente nesse modelo, permitindo que sua loja automatize ações importantes baseadas no ciclo de vida dos pedidos, sem depender de ferramentas específicas e frequentemente custosas de terceiros.

Um dos principais usos deste projeto é integrar a VTEX ao BotConversa, criando automações que notificam os clientes via WhatsApp sobre o status do pedido, garantindo uma comunicação eficiente e personalizada.

---

### ✨ Como este Programa funciona na prática

O **VTEX Legacy Order Tracker** funciona como um monitor de pedidos, com os seguintes recursos:

* **Agendamento de Consultas:** A aplicação roda em uma thread separada e agenda consultas periódicas à API de OMS da VTEX. Padrão: a cada 30 minutos (configurável via código).

* **Filtragem Inteligente:** O sistema filtra apenas os pedidos novos ou atualizados, priorizando por padrão os da política comercial principal (Sales Channel: 1).

* **Identificação de "Order Placed":** Um pedido com `status = payment-approved` ou `ready-for-handling` é considerado como "colocado" (orderPlaced).

* **Gravação no Master Data v1:** Os dados desses pedidos são gravados em uma entidade personalizada (ex: `OrderEvents`) no Master Data.

* **Disparo de Webhooks via Triggers:** Você pode configurar triggers no Master Data para enviar POSTs automáticos para webhooks externos (ex: BotConversa, Zapier).

#### Exemplo: Notificação WhatsApp

1. O pedido é salvo no Master Data.
2. Uma trigger dispara um POST para o webhook do BotConversa.
3. O cliente recebe uma mensagem no WhatsApp minutos após a compra, informando que o pedido foi recebido.

---

### ⚠️ Observações Importantes

* **Não é Tempo Real:** A principal limitação deste método é que ele não oferece monitoramento em tempo real. A "atualidade" da informação depende diretamente da frequência do seu polling (intervalo de consulta).
* **Uso Responsável da API:** A API de OMS da VTEX é robusta e suporta um volume considerável de requisições. No entanto, é crucial utilizá-la com responsabilidade e não abusar da frequência de consultas para evitar bloqueios ou sobrecarga desnecessária. Como se trata de uma solução de baixo custo, é mais indicado para lojas de médio e pequeno porte que não possuem um grande volume de pedidos.
* **Paginação:** O app consulta 25 pedidos por página. Isso pode ser ajustado para melhorar o desempenho.

---

### 🧭 Próximos Passos

* **Expansão de Status:** Tratar outras mudanças de status e registrar no Master Data.
* **Múltiplos Webhooks:** Notificações ao longo de todo o ciclo de compra (ex: "Faturado", "Saiu para entrega", "Entregue").
* **Otimização da Paginação:** Lógica refinada para consultar e processar dados distribuídos em várias páginas.
* **Dashboards:** Integração com visualizadores para relatórios dos pedidos processados.

---

### 🛠️ Tecnologias Utilizadas

* **Python:** Linguagem principal do desenvolvimento.
* **CustomTkinter:** Biblioteca para a interface gráfica de usuário (GUI).
* **Requests:** Para fazer requisições HTTP à API da VTEX.
* **python-dotenv:** Para gerenciar variáveis de ambiente (chaves de API, etc.).
* **PyInstaller:** Para empacotar o aplicativo em um executável (opcional).

---

### 🚀 Como Usar/Executar

1. **Clone o repositório:**

```bash
git clone https://github.com/nathvegi/vtexlegacy_order_tracker.git
cd vtexlegacy_order_tracker
```

2. **Crie e ative um ambiente virtual:**

```bash
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate
```

3. **Instale as dependências:**

```bash
pip install python-dotenv requests customtkinter
```

4. **Configure o arquivo `.env`:**

```env
VTEX_ACCOUNT="seuaccountvtex"
VTEX_ENVIRONMENT="suaenvironmentvtex" # Ex: "vtexcommercestable"
VTEX_APP_KEY="SUA_APP_KEY_AQUI"
VTEX_APP_TOKEN="SUA_APP_TOKEN_AQUI"
```

5. **Crie a entidade `OrderEvents` no Master Data v1** com os campos:

* `orderId` (text)
* `status` (text)
* `creationDate` (datetime)
* `totalValue` (decimal)
* `clientEmail` (text)
* `clientPhoneCell` (text)
* `clientName` (text)

6. **Execute o aplicativo:**

```bash
python app.py
```

7. **(Opcional) Geração de executável:**

```bash
pyinstaller --onefile --windowed --icon=icon.ico app.py
```

---

### 🤝 Contribuições

Contribuições são bem-vindas! Abra issues ou pull requests com melhorias ou correções.

---

### 📄 Licença

Este projeto está licenciado sob a Licença MIT.

