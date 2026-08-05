"""
Bot Telegram para notificações de vendas via UTMify.
Recebe webhooks da UTMify e envia mensagens formatadas no Telegram.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# ============================================================
# CONFIGURAÇÃO — preencha com seus dados
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # opcional, para validar origem
# ============================================================

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def enviar_telegram(mensagem: str):
    """Envia uma mensagem para o chat/grupo configurado no Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def formatar_valor(valor) -> str:
    """Formata valor numérico para BRL."""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(valor)


def formatar_mensagem(dados: dict) -> str:
    """
    Monta a mensagem de notificação a partir do payload da UTMify.
    Adapta-se aos campos presentes — se um campo não existir, é omitido.
    """
    # Campos comuns no webhook da UTMify
    status = dados.get("status", dados.get("transaction_status", ""))
    produto = dados.get("product_name", dados.get("prod_name", dados.get("product", "")))
    valor = dados.get("amount", dados.get("value", dados.get("price", "")))
    comissao = dados.get("commission", dados.get("comission", ""))
    comprador = dados.get("customer_name", dados.get("buyer_name", dados.get("name", "")))
    email = dados.get("customer_email", dados.get("buyer_email", dados.get("email", "")))
    telefone = dados.get("customer_phone", dados.get("phone", ""))
    pagamento = dados.get("payment_method", dados.get("payment_type", ""))
    transacao = dados.get("transaction_id", dados.get("transaction", dados.get("sale_id", "")))
    plataforma = dados.get("platform", dados.get("source", ""))
    src = dados.get("src", "")
    sck = dados.get("sck", "")
    utm_source = dados.get("utm_source", "")
    utm_medium = dados.get("utm_medium", "")
    utm_campaign = dados.get("utm_campaign", "")

    # Ícone baseado no status
    icones = {
        "approved": "✅",
        "completed": "✅",
        "paid": "✅",
        "refunded": "🔄",
        "canceled": "❌",
        "cancelled": "❌",
        "chargeback": "⚠️",
        "waiting_payment": "⏳",
        "pending": "⏳",
    }
    icone = icones.get(status.lower(), "🔔") if status else "🔔"

    # Montar mensagem
    linhas = [f"{icone} <b>NOVA NOTIFICAÇÃO DE VENDA</b> {icone}", ""]

    if status:
        linhas.append(f"<b>Status:</b> {status.upper()}")
    if produto:
        linhas.append(f"<b>Produto:</b> {produto}")
    if valor:
        linhas.append(f"<b>Valor:</b> {formatar_valor(valor)}")
    if comissao:
        linhas.append(f"<b>Comissão:</b> {formatar_valor(comissao)}")
    if pagamento:
        linhas.append(f"<b>Pagamento:</b> {pagamento}")
    if transacao:
        linhas.append(f"<b>Transação:</b> <code>{transacao}</code>")

    # Dados do comprador
    if comprador or email or telefone:
        linhas.append("")
        linhas.append("👤 <b>Comprador</b>")
        if comprador:
            linhas.append(f"  Nome: {comprador}")
        if email:
            linhas.append(f"  Email: {email}")
        if telefone:
            linhas.append(f"  Tel: {telefone}")

    # UTMs / rastreamento
    utms = []
    if src:
        utms.append(f"src={src}")
    if sck:
        utms.append(f"sck={sck}")
    if utm_source:
        utms.append(f"utm_source={utm_source}")
    if utm_medium:
        utms.append(f"utm_medium={utm_medium}")
    if utm_campaign:
        utms.append(f"utm_campaign={utm_campaign}")

    if utms:
        linhas.append("")
        linhas.append("📊 <b>Rastreamento</b>")
        for u in utms:
            linhas.append(f"  {u}")

    if plataforma:
        linhas.append("")
        linhas.append(f"<b>Plataforma:</b> {plataforma}")

    linhas.append("")
    linhas.append(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    return "\n".join(linhas)


# ============================================================
# ROTAS
# ============================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    """Endpoint que recebe o POST da UTMify."""

    # Validação opcional de segredo
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret", request.args.get("secret", ""))
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    # Aceita JSON ou form-encoded
    if request.is_json:
        dados = request.get_json(force=True)
    else:
        dados = request.form.to_dict()

    app.logger.info("Webhook recebido: %s", json.dumps(dados, ensure_ascii=False, default=str))

    try:
        mensagem = formatar_mensagem(dados)
        enviar_telegram(mensagem)
        app.logger.info("Notificação enviada com sucesso.")
        return jsonify({"ok": True}), 200
    except Exception as e:
        app.logger.error("Erro ao enviar notificação: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check — útil para monitoramento."""
    return jsonify({"status": "ok"}), 200


@app.route("/test", methods=["GET"])
def test():
    """Envia uma mensagem de teste para verificar se o bot está funcionando."""
    try:
        enviar_telegram("🧪 <b>Teste!</b>\nSeu bot de vendas está funcionando corretamente.")
        return jsonify({"ok": True, "message": "Mensagem de teste enviada!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
