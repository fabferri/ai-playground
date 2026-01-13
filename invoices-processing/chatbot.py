"""
Invoice Chatbot - RAG-based Q&A using Azure AI Search + Azure OpenAI

This chatbot:
1. Takes user questions about invoices
2. Searches the Azure AI Search index for relevant invoices
3. Uses Azure OpenAI to generate natural language answers
"""

import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Load environment variables from .env file
load_dotenv()

# Configuration
SEARCH_ENDPOINT = os.getenv('SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('SEARCH_KEY')
SEARCH_INDEX_NAME = os.getenv('SEARCH_INDEX_NAME')

OPENAI_ENDPOINT = os.getenv('OPENAI_ENDPOINT')
OPENAI_KEY = os.getenv('OPENAI_KEY')
OPENAI_DEPLOYMENT = os.getenv('OPENAI_DEPLOYMENT')


def search_invoices(query: str, top: int = None, filter_expression: str = None):
    """Search the invoice index and return relevant results
    
    Args:
        query: Search query string
        top: Maximum number of results to return (None = return all results)
        filter_expression: OData filter expression for filtering results
    """
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        search_params = {
            "search_text": query,
            "select": ["invoice_id", "vendor", "invoice_date", "due_date", 
                      "total", "currency", "content"]
        }
        
        # Only add top parameter if specified
        if top is not None:
            search_params["top"] = top
            
        # Add filter if specified
        if filter_expression:
            search_params["filter"] = filter_expression
        
        results = search_client.search(**search_params)
        
        return list(results)
    finally:
        search_client.close()


def create_context_from_results(results):
    """Convert search results into context for the LLM"""
    if not results:
        return "No relevant invoices found in the database."
    
    context_parts = []
    for i, result in enumerate(results, 1):
        invoice_info = f"""
Invoice {i}:
- ID: {result.get('invoice_id', 'N/A')}
- Vendor: {result.get('vendor', 'N/A')}
- Date: {result.get('invoice_date', 'N/A')}
- Due Date: {result.get('due_date', 'N/A')}
- Total: {result.get('currency', '')} {result.get('total', 0):.2f}
- Content: {result.get('content', '')[:300]}
"""
        context_parts.append(invoice_info.strip())
    
    return "\n\n".join(context_parts)


def ask_chatbot(question: str, conversation_history=None):
    """
    Ask the chatbot a question about invoices
    
    Args:
        question: User's question
        conversation_history: Previous messages for context (optional)
    
    Returns:
        The chatbot's answer
    """
    # Step 1: Search for relevant invoices
    print(f"\nSearching for relevant invoices...")
    
    # Check if query mentions specific months/dates and build filter
    filter_expr = None
    import re
    
    # Detect month and year patterns
    month_year_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', question, re.IGNORECASE)
    
    if month_year_match:
        month_name = month_year_match.group(1)
        year = month_year_match.group(2)
        
        # Map month names to numbers
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        month_num = month_map.get(month_name.lower())
        
        if month_num:
            # Create OData filter for the month (using string comparison since invoice_date is String type)
            start_date = f"{year}-{month_num}-01"
            # Calculate last day of month (simplified - assumes 31 days)
            end_date = f"{year}-{month_num}-31"
            filter_expr = f"invoice_date ge '{start_date}' and invoice_date le '{end_date}'"
            print(f"   Applying date filter: {month_name} {year}")
    
    search_results = search_invoices(question, filter_expression=filter_expr)
    
    if not search_results:
        print("   No invoices found.")
    else:
        print(f"   Found {len(search_results)} relevant invoice(s)")
        # Limit context to top 20 results to avoid exceeding token limits
        if len(search_results) > 20:
            print(f"   Using top 20 most relevant for context (to avoid token limits)")
            search_results = search_results[:20]
    
    # Step 2: Create context from search results
    context = create_context_from_results(search_results)
    
    # Step 3: Build the prompt for Azure OpenAI
    system_message = """You are an invoice assistant. Answer questions about invoices based on the provided context.

Guidelines:
- Always cite the invoice ID when referencing specific invoices
- If the answer isn't in the context, say you don't have that information
- Be concise and accurate for specific questions
- Format numbers and dates clearly
- When asked to "show" or "list" invoices, display ALL invoices from the context, not just a few examples"""

    user_message = f"""Context from invoice database:
{context}

User question: {question}

Please answer the question based on the invoice information provided above."""

    # Step 4: Call Azure OpenAI
    client = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_key=OPENAI_KEY,
        api_version="2024-08-01-preview"
    )
    
    messages = conversation_history or []
    if not messages:
        messages.append({"role": "system", "content": system_message})
    
    messages.append({"role": "user", "content": user_message})
    
    print("\nGenerating response...")
    try:
        response = client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=2000  # Increased to allow listing many invoices
        )
        
        answer = response.choices[0].message.content
        
        # Debug: Check if answer is empty
        if not answer:
            print("   WARNING: Received empty response from OpenAI")
            answer = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
        
    except Exception as e:
        print(f"   ERROR calling OpenAI: {e}")
        raise
    
    # Add assistant response to history
    messages.append({"role": "assistant", "content": answer})
    
    return answer, messages


def interactive_chat():
    """Run an interactive chatbot session"""
    print("="*70)
    print("INVOICE CHATBOT - Powered by Azure AI Search + OpenAI")
    print("="*70)
    print("\nAsk me questions about your invoices!")
    print("Examples:")
    print("  - What invoices do we have from Contoso?")
    print("  - Show me invoices from April 2025")
    print("  - What's the total amount for invoice INV-2025-0001?")
    print("  - Which vendor has the most recent invoice?")
    print("\nType 'quit' or 'exit' to end the conversation.\n")
    
    conversation_history = None
    
    while True:
        # Get user input
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\nGoodbye! Thanks for chatting.")
            break
        
        try:
            # Get chatbot response
            answer, conversation_history = ask_chatbot(user_input, conversation_history)
            
            # Display response
            print(f"\nAssistant: {answer}\n")
            print("-"*70 + "\n")
            
        except Exception as e:
            print(f"\nError: {e}\n")
            print("Please try asking your question differently.\n")


def single_question_demo():
    """Demo with a single question"""
    print("="*70)
    print("INVOICE CHATBOT DEMO")
    print("="*70)
    
    # Example questions
    questions = [
        "What invoices do we have in the database?",
        "Show me invoices from Contoso",
        "Which invoice is due earliest?"
    ]
    
    print("\nExample questions:\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")
    
    print("\n" + "="*70)
    
    # Ask first question
    question = questions[0]
    print(f"\nQuestion: {question}")
    
    answer, _ = ask_chatbot(question)
    
    print(f"\n{'='*70}")
    print("ANSWER:")
    print("="*70)
    print(answer)
    print("="*70)


if __name__ == "__main__":
    import sys
    
    # Check if user wants interactive mode or demo
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        single_question_demo()
    else:
        interactive_chat()
