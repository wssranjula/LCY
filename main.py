import streamlit as st
st.set_page_config(page_title="StyleBot - LCY AI Shopping Assistant", page_icon="👗", layout="wide")

from langchain_community.document_loaders import RecursiveUrlLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter  # Added text splitter
import re
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from prompts import agent_prompt

# Define the StyleBot prompt
stylebot_prompt = """
You are "StyleBot," an AI assistant for LCY apparel e-commerce company. Your primary goal is to assist customers in finding the perfect clothing items and provide accurate, helpful product information. You are friendly, approachable, and knowledgeable about fashion, prioritizing the customer’s needs over pushing sales.

For each user query, you will receive relevant product information from our database. Use this information to directly answer the user’s questions about products, offer tailored recommendations, or assist with their shopping needs. Keep your responses conversational, clear, and focused on the user’s intent—never include code snippets, technical jargon, or unrelated details.

If the provided product information is insufficient or the requested item isn’t available:
1. Be honest and say, “I couldn’t find that exact item in our collection,” or similar, to set clear expectations.
2. Ask the user for more details (e.g., “Could you tell me more about the style or occasion you’re looking for?”) to refine the request.
3. Only suggest alternatives or similar items if they genuinely match the user’s query, and present them as options—not as a hard sell (e.g., “We don’t have that, but here’s something similar you might like: [details]. Does that work for you?”).
4. If no relevant alternatives exist, offer general fashion advice or invite the user to check back later (e.g., “I don’t have anything close to that right now, but our collection updates often—want me to suggest something else?”).

Avoid fabricating details or forcing a sale when information is lacking. Your tone should remain upbeat and supportive, ensuring the user feels heard and assisted.

"""

# Load API keys from Streamlit secrets
google_api_key = st.secrets["GOOGLE_API_KEY"]
openai_api_key = st.secrets["OPENAI_API_KEY"]

# Initialize the LLM (Google Gemini)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    api_key=google_api_key
)

# Define the HTML extractor
def bs4_extractor(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return re.sub(r"\n\n+", "\n\n", soup.text).strip()

# Load, split, and index web data with OpenAI embeddings
@st.cache_resource
def load_and_index_data(url):
    try:
        loader = RecursiveUrlLoader(url, extractor=bs4_extractor)
        raw_docs = loader.load()
        if not raw_docs:
            raise ValueError("No documents loaded from the URL.")
        
        # Add text splitting to break documents into smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Adjust size based on your needs
            chunk_overlap=200,  # Overlap to maintain context
            length_function=len,
        )
        docs = text_splitter.split_documents(raw_docs)
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_api_key
        )
        vector_store = FAISS.from_documents(docs, embeddings)
        return vector_store
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

# Initialize the vector store and retriever
url = "https://lcy.lk/"
vector_store = load_and_index_data(url)
retriever = vector_store.as_retriever(search_kwargs={"k": 3}) if vector_store else None

# Define search_products function to retrieve relevant product information
def search_products(query):
    if not retriever:
        return "Sorry, I couldn't load the product data. Please try again later."
    docs = retriever.get_relevant_documents(query)
    # Filter out any code-like content from retrieved docs
    filtered_content = "\n\n".join(
        [doc.page_content for doc in docs if not re.search(r"```|import |def |class ", doc.page_content)]
    )
    return filtered_content if filtered_content else "No relevant products found."

# Add custom CSS for styling (unchanged)
st.markdown("""
    <style>
        .main { background-color: #f5f5f5; }
        .stChatMessage { border-radius: 10px; padding: 10px; margin-bottom: 10px; }
        .stChatMessage.user { background-color: #e0f7fa; }
        .stChatMessage.assistant { background-color: #fff; border: 1px solid #ddd; }
        .stTextInput > div > div > input { border-radius: 5px; padding: 10px; }
        .header { text-align: center; color: #333; margin-bottom: 20px; }
        .welcome { text-align: center; color: #666; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Header (unchanged)
st.markdown("<h1 class='header'>👗 StyleBot - LCY Shopping Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p class='welcome'>Find the perfect outfit with ease. Let StyleBot assist you!</p>", unsafe_allow_html=True)

# Initialize session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Hi there! I’m StyleBot, your shopping assistant. How can I help you find the perfect outfit today?"})

# Display conversation history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
user_input = st.chat_input("Type your message here... (e.g., 'I need a red dress for a party')")

if user_input:
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Show spinner while processing the response
    with st.spinner("StyleBot is finding the perfect match for you..."):
        # Retrieve relevant product information
        relevant_docs = search_products(user_input)

        # Construct messages for the LLM
        messages = [
            ("system", stylebot_prompt),  # Updated to use stylebot_prompt directly
        ] + [(msg["role"], msg["content"]) for msg in st.session_state.messages[:-1]] + [
            ("human", f"{st.session_state.messages[-1]['content']}\n\nRelevant product information: {relevant_docs}")
        ]

        # Generate response
        try:
            response = llm.invoke(messages).content
            # Post-process to remove any lingering code-like content
            if re.search(r"```|import |def |class ", response):
                response = "Let me help you with that in a simpler way! " + response.split("```")[0].strip()
        except Exception as e:
            response = f"Sorry, something went wrong: {str(e)}"
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)