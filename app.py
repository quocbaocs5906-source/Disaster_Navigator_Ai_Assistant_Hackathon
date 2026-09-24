import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fema_service import (
    get_fema_fraud_guidance,
    search_drc_by_zip,
    get_disaster_declarations,
)

# Load environment variables from .env file
load_dotenv()

# Get GEMINI API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

# Page Configuration
st.set_page_config(
    page_title="AI Disaster Assistance Navigator",
    page_icon="🚨",
    layout="wide"
)

# Dictionary lời chào theo ngôn ngữ
WELCOME_MESSAGES = {
    "English": "Hello! I am your AI Disaster Assistance Navigator. How can I help you or your community with disaster relief and official FEMA resources today?",
    "Tiếng Việt": "Xin chào! Tôi là Trợ lý Điều hướng Trợ cấp Thiên tai AI. Tôi có thể giúp gì cho bạn hoặc cộng đồng của bạn về hỗ trợ thiên tai và các nguồn lực chính thức từ FEMA hôm nay?",
    "Español": "¡Hola! Soy su Navegador de Asistencia para Desastres con IA. ¿Cómo puedo ayudarle a usted o a su comunidad hoy con los recursos oficiales de FEMA?",
    "Français": "Bonjour! Je suis votre Navigateur d'Assistance en Cas de Catastrophe IA. Comment puis-je vous aider, vous ou votre communauté, aujourd'hui avec les ressources officielles de la FEMA?"
}

# ------------------------------------------------------------------------------
# SIDEBAR: SETTINGS & ACCESSIBILITY
# ------------------------------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Settings & Accessibility")
    
    # Multi-language selection
    selected_language = st.selectbox(
        "🗣️ Response Language:",
        ["English", "Tiếng Việt", "Español", "Français"],
        help="Select the language for the AI Assistant"
    )

    # High Contrast & Large Text Toggle (Accessibility)
    high_contrast = st.toggle("🌗 High Contrast / Large Text")
    
    if high_contrast:
        st.markdown("""
            <style>
                .stApp { background-color: #000000; color: #FFFF00; }
                p, li, span, div, input, button { font-size: 18px !important; }
                .stTextInput > div > div > input { border: 2px solid #FFFF00 !important; }
                .stButton > button { border: 2px solid #FFFF00 !important; font-weight: bold; }
            </style>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.title("📌 Disaster Resources")
    
    # 1. DRC Search Box
    st.markdown("Find nearby Disaster Recovery Centers (DRC) using your ZIP code.")
    zip_code = st.text_input("Enter 5-digit ZIP Code:", max_chars=5)

    if st.button("🔍 Search Centers", use_container_width=True):
        if zip_code and zip_code.isdigit() and len(zip_code) == 5:
            with st.spinner("Searching FEMA registry..."):
                drc_results = search_drc_by_zip(zip_code)
                if "Error" in drc_results or "No active" in drc_results or "Could not" in drc_results:
                    st.warning(drc_results)
                else:
                    st.success("Disaster Recovery Centers Found:")
                    st.markdown(drc_results)
        else:
            st.error("Please enter a valid 5-digit US ZIP code.")

    st.markdown("---")

    # 2. Recent Disaster Declarations Box
    st.markdown("Check recent 5 disaster declarations by US State.")
    state_code = st.text_input("Enter 2-letter State Code:", max_chars=2, placeholder="e.g. CA, TX, FL").upper()

    VALID_US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", 
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", 
        "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", 
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", 
        "WI", "WY", "DC", "PR", "VI", "GU", "MP", "AS"
    }

    if st.button("📢 Check Recent Disasters", use_container_width=True):
        if state_code in VALID_US_STATES:
            with st.spinner(f"Fetching disaster data for {state_code}..."):
                disaster_results = get_disaster_declarations(state_code)
                if "Error" in disaster_results or "System Alert" in disaster_results:
                    st.error(disaster_results)
                elif "No recent" in disaster_results:
                    st.info(disaster_results)
                else:
                    st.success(f"Recent Disasters in {state_code}:")
                    st.markdown(disaster_results)
        else:
            st.error("Please enter a valid 2-letter US state code (e.g., CA, NY, FL).")

    st.markdown("---")
    st.info(
        "💡 **Emergency Note:** If you are in immediate danger, please call 911 or your local emergency services directly."
    )

# ------------------------------------------------------------------------------
# MAIN AREA: Header & Title
# ------------------------------------------------------------------------------
st.title("🚨 AI Disaster Assistance Navigator")
st.caption("Emergency disaster information & AI assistant powered by official FEMA data.")

# ------------------------------------------------------------------------------
# CHAT SESSION & LANGUAGE STATE MANAGEMENT
# ------------------------------------------------------------------------------
# Reset hội thoại khi chuyển đổi ngôn ngữ để cập nhật System Prompt & Lời chào phù hợp
if "current_language" not in st.session_state or st.session_state.current_language != selected_language:
    st.session_state.current_language = selected_language
    st.session_state.ui_messages = [
        {"role": "assistant", "content": WELCOME_MESSAGES.get(selected_language, WELCOME_MESSAGES["English"])}
    ]
    # Reset chat_session để khởi tạo lại với system instruction ngôn ngữ mới
    if "chat_session" in st.session_state:
        del st.session_state["chat_session"]

# Khởi tạo Gemini Chat Session đơn nhất (Dùng chat_session.send_message_stream)
if "chat_session" not in st.session_state and GEMINI_API_KEY:
    fraud_rules = get_fema_fraud_guidance()
    
    system_prompt = f"""
You are an empathetic, highly clear, and authoritative AI Disaster Assistance Navigator.
Your primary job is to guide disaster-affected residents to official resources, emergency support, and FEMA assistance programs.

CRITICAL GUIDELINES:
1. Always prioritize safety and official channels.
2. Maintain strict adherence to official FEMA Fraud Prevention rules:
{fraud_rules}
3. If users ask about applying for disaster assistance, clearly state that FEMA never charges fees.
4. Keep explanations concise, actionable, and formatted nicely with Markdown bullet points.
5. IMPORTANT TOOL USE INSTRUCTION: If the user provides a US ZIP code or a state abbreviation, you MUST call your tools (`search_drc_by_zip` or `get_disaster_declarations`) to fetch real-time FEMA data before answering. Do NOT hallucinate or guess locations.

6. 📝 REQUIRED DOCUMENTS FOR FEMA ASSISTANCE: 
When a user asks how to apply for assistance or what they need, you MUST proactively list the standard required documents:
- A current phone number where they can be contacted.
- Address of the damaged home and current address.
- Social Security Number (SSN).
- A general list of damage and losses (photos/videos if possible).
- Banking information (if they choose direct deposit).
- Insurance information (policy number/company name if applicable).

7. 🔒 PII & SENSITIVE DATA SAFEGUARD (STRICT RULE):
If the user inputs personal sensitive information in the chat (such as an actual Social Security Number, bank account/credit card details, driver's license, or official ID numbers), IMMEDIATELY warn them NOT to post sensitive information here. Remind them gently that this AI chat cannot process applications and that sensitive details should ONLY be submitted via official channels at DisasterAssistance.gov or by calling 1-800-621-3362.

🚨 ESCALATION PROTOCOL (MANDATORY & MULTI-LANGUAGE TAGGING):
You must dynamically evaluate every user prompt for sensitive, ambiguous, urgent, or high-impact scenarios.
- TRIGGERS: Immediate physical danger, trapped individuals, severe medical emergencies, mental health crises, sudden homelessness, domestic violence, or complex legal disputes regarding FEMA claims.
- MANDATORY TAGGING RULE: If an escalation trigger is detected, you MUST prepend your response with the exact tag `[ESCALATE]` at the very beginning of your output.
- ESCALATION ACTION: Compassionately explain in the target language (**{selected_language}**) that this situation requires immediate human assistance. Direct them to the official FEMA Helpline (1-800-621-3362) for human support, or explicitly command them to call 911 if it is a life-threatening emergency.

🌐 LANGUAGE & ACCESSIBILITY MANDATE:
You MUST communicate directly with the user exclusively in **{selected_language}**. Translate explanations naturally, but keep official FEMA program names (e.g., "Disaster Recovery Center", "Individual Assistance") in English in parentheses to prevent confusion when they search official sites.
"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[search_drc_by_zip, get_disaster_declarations],
            temperature=0.2,
        )
        # Sử dụng model phiên bản mới ổn định
        st.session_state.chat_session = client.chats.create(
            model="gemini-3.5-flash",
            config=config
        )
    except Exception as e:
        st.error(f"Failed to initialize Gemini Client: {e}")

# ------------------------------------------------------------------------------
# CHAT HISTORY DISPLAY
# ------------------------------------------------------------------------------
for message in st.session_state.ui_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ------------------------------------------------------------------------------
# CHAT INPUT & RESPONSE STREAMING
# ------------------------------------------------------------------------------
if prompt := st.chat_input("Ask about FEMA assistance, DRC locations, or application help..."):
    # Hiển thị tin nhắn người dùng
    st.session_state.ui_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Sinh phản hồi từ Assistant
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        if not GEMINI_API_KEY:
            st.error("Missing GEMINI_API_KEY. Please check your .env file or Streamlit secrets.")
        else:
            try:
                fraud_rules = get_fema_fraud_guidance()
                
                system_prompt = f"""
You are an empathetic, highly clear, and authoritative AI Disaster Assistance Navigator.
Your primary job is to guide disaster-affected residents to official resources, emergency support, and FEMA assistance programs.

CRITICAL GUIDELINES:
1. Always prioritize safety and official channels.
2. Maintain strict adherence to official FEMA Fraud Prevention rules:
{fraud_rules}
3. If users ask about applying for disaster assistance, clearly state that FEMA never charges fees.
4. Keep explanations concise, actionable, and formatted nicely with Markdown bullet points.
5. IMPORTANT TOOL USE INSTRUCTION: If the user provides a US ZIP code or a state abbreviation, you MUST call your tools (`search_drc_by_zip` or `get_disaster_declarations`) to fetch real-time FEMA data before answering. Do NOT hallucinate or guess locations.

6. 📝 REQUIRED DOCUMENTS FOR FEMA ASSISTANCE: 
When a user asks how to apply for assistance or what they need, you MUST proactively list the standard required documents:
- A current phone number where they can be contacted.
- Address of the damaged home and current address.
- Social Security Number (SSN).
- A general list of damage and losses (photos/videos if possible).
- Banking information (if they choose direct deposit).
- Insurance information (policy number/company name if applicable).

7. 🔒 PII & SENSITIVE DATA SAFEGUARD (STRICT RULE):
If the user inputs personal sensitive information in the chat (such as an actual Social Security Number, bank account/credit card details, driver's license, or official ID numbers), IMMEDIATELY warn them NOT to post sensitive information here. Remind them gently that this AI chat cannot process applications and that sensitive details should ONLY be submitted via official channels at DisasterAssistance.gov or by calling 1-800-621-3362.

🚨 ESCALATION PROTOCOL (MANDATORY & MULTI-LANGUAGE TAGGING):
You must dynamically evaluate every user prompt for sensitive, ambiguous, urgent, or high-impact scenarios.
- TRIGGERS: Immediate physical danger, trapped individuals, severe medical emergencies, mental health crises, sudden homelessness, domestic violence, or complex legal disputes regarding FEMA claims.
- MANDATORY TAGGING RULE: If an escalation trigger is detected, you MUST prepend your response with the exact tag `[ESCALATE]` at the very beginning of your output.
- ESCALATION ACTION: Compassionately explain in the target language (**{selected_language}**) that this situation requires immediate human assistance. Direct them to the official FEMA Helpline (1-800-621-3362) for human support, or explicitly command them to call 911 if it is a life-threatening emergency.

🌐 LANGUAGE & ACCESSIBILITY MANDATE:
You MUST communicate directly with the user exclusively in **{selected_language}**. Translate explanations naturally, but keep official FEMA program names (e.g., "Disaster Recovery Center", "Individual Assistance") in English in parentheses to prevent confusion when they search official sites.
"""

                # Dùng Context Manager để đảm bảo Client được khởi tạo mới và đóng an toàn
                with genai.Client(api_key=GEMINI_API_KEY) as client:
                    
                    # Chuyển đổi ui_messages thành cấu trúc contents của Gemini
                    contents = []
                    for msg in st.session_state.ui_messages:
                        role = "user" if msg["role"] == "user" else "model"
                        contents.append(
                            types.Content(
                                role=role,
                                parts=[types.Part.from_text(text=msg["content"])]
                            )
                        )

                    config = types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[search_drc_by_zip, get_disaster_declarations],
                        temperature=0.2,
                    )

                    # Gọi stream trực tiếp thông qua client.models
                    response = client.models.generate_content_stream(
                        model="gemini-3.5-flash",
                        contents=contents,
                        config=config
                    )

                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            display_text = full_response.replace("[ESCALATE]", "")
                            message_placeholder.markdown(display_text + "▌")
                    
                    clean_response = full_response.replace("[ESCALATE]", "").strip()
                    message_placeholder.markdown(clean_response)

                # --- LANGUAGE-INDEPENDENT UI ESCALATION INTERCEPTOR ---
                if "[ESCALATE]" in full_response or "1-800-621-3362" in full_response or "911" in full_response:
                    st.error("🚨 **SYSTEM ESCALATION TRIGGERED** 🚨\n\nYour situation requires immediate human assistance. Please call the **FEMA Helpline at 1-800-621-3362** or **911** for life-threatening emergencies.")
                # -----------------------------------------------------

                # Lưu phản hồi vào lịch sử giao diện
                st.session_state.ui_messages.append({"role": "assistant", "content": clean_response})

            except Exception as e:
                st.error(f"Error communicating with Gemini API: {e}")