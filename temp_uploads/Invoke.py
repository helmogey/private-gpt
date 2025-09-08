

from transformers import AutoTokenizer, AutoModelForCausalLM, BertTokenizer, BertForSequenceClassification, T5Tokenizer, T5ForConditionalGeneration
from sentence_transformers import SentenceTransformer
import chromadb



def load_model_sbert(device, model_save_path='./models/sbert/'):
    model = BertForSequenceClassification.from_pretrained(model_save_path)
    tokenizer = BertTokenizer.from_pretrained(model_save_path)
    print("SBERT Model and tokenizer loaded from local storage.")
    model.to(device)
    return model, tokenizer

def load_llama(save_directory = "../models/llama3_2_8B_Instruct"):

    model = AutoModelForCausalLM.from_pretrained(save_directory)
    tokenizer = AutoTokenizer.from_pretrained(save_directory)
    print("LLaMA Model and tokenizer loaded.")
    return model, tokenizer

def load_T5(save_directory='./models/T5_3B'):
    model = T5ForConditionalGeneration.from_pretrained(save_directory)
    tokenizer = T5Tokenizer.from_pretrained(save_directory)
    print(f"T5 Model and tokenizer loaded from {save_directory}.")
    return model, tokenizer





def load_model(model_type):
    global model, tokenizer
    model_path = ".."
    if model_type == "T5_3B":
        model, tokenizer = load_T5(model_path + "/models/T5_3B")
    elif model_type == "T5_small":
        model, tokenizer = load_T5(model_path + "/models/T5_small")
    elif model_type == "T5_large":
        model, tokenizer = load_T5(model_path + "/models/T5_large")
    elif model_type == "T5_11B":
        model, tokenizer = load_T5(model_path + "/models/T5_11B")
    elif model_type == "llama_8B_Instruct":
        model, tokenizer = load_llama()
    elif model_type == "llama_1B_Instruct":
        model, tokenizer = load_llama(model_path + "/models/llama_1B_Instruct")
    elif model_type == "llama_1B_Basic":
        model, tokenizer = load_llama(model_path + "/models/llama_1B_Basic")
    elif model_type == "llama_3B_Instruct":
        model, tokenizer = load_llama(model_path + "/models/llama_3B_Instruct")
    elif model_type == "llama_3B_Basic":
        model, tokenizer = load_llama(model_path + "/models/llama_3B_Basic")
    elif model_type == "llama_70B_Instruct":
        model, tokenizer = load_llama(model_path + "/models/llama_70B_Instruct")
    elif model_type == "sbert":
        model, tokenizer = load_model_sbert(device)
    else:
        raise ValueError("Unsupported model type")
    return model, tokenizer




def invoke_llama(model, tokenizer, msg, context, flag=True, max_length=64000):
    """
    Invokes the Llama model with a strict prompt using the given message and context.

    Args:
        msg (str): The question or message to query the model.
        context (str): The structured context for the model to refer to.
        flag (bool): Additional flag for flexibility in model behavior (default True).
        max_length (int): Maximum length of the model's output (default 2048) and max is max_length=128000.

    Returns:
        str: The model's response.
    """
    context = context[0:max_length - 5]
    print(context)
    print("*"*50)
    print(msg)

    # Construct a strict prompt for the model


    strict_prompt = f"""Answer the following question using ONLY the information provided in the context below.  Do NOT include any explanations, reasoning, introductory phrases, conclusions, or any text other than the direct answer. If the answer cannot be found in the context, respond with "No answer." and nothing else.

    Context:
    {context}

    Question:
    {msg}

    Answer:"""

    # strict_prompt = f"""
    #         Knowing the following information:
    #         {context}

    #         Question:
    #         {msg}
    #         **Instructions:**
    #         - Answer the question using ONLY the information provided in the context above.
    #         - Do NOT include any explanations, reasoning, introductory phrases, conclusions, or any text other than the direct answer.
    #         - If the answer cannot be found in the context, respond with "No answer." and nothing else.
    #         Answer:"""

    # Tokenize the input prompt
    inputs = tokenizer(strict_prompt, return_tensors='pt', max_length=max_length, truncation=True)

    # Generate a response from the model
    output_ids = model.generate(
        **inputs,
        max_length=max_length,
        temperature=0.5,  # Deterministic output
        top_p=0.5,  # Nucleus sampling for coherent responses
        repetition_penalty=1.1,  # Avoid repetitive output
        eos_token_id=tokenizer.eos_token_id
    )

    # Decode the generated text
    response = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # Extract and clean the response after "Answer:"
    return response.split("Answer:")[-1].strip()






###################################################################################################################
# fetch the context
###################################################################################################################


def search_and_answer(query_text, top_no=1, n_results=10, target_similarity = 0.3):
    results = collection.query(query_texts=[query_text], n_results=n_results)

    if results["documents"] == [[]] or results["ids"] == [[]]:
        return {"answer": "No relevant data found.", "chunk": None}

    all_chunks = [doc for sublist in results["documents"] for doc in sublist]
    all_ids = [doc_id for sublist in results["ids"] for doc_id in sublist]

    # Ensure embedding_model is defined
    query_embedding = embedding_model.encode(query_text)

    chunk_embeddings = embedding_model.encode(all_chunks)
    similarities = [float(query_embedding @ chunk_emb.T) for chunk_emb in chunk_embeddings]

    print("*"*50)
    print(similarities)
    print("*"*50)


    # remove similarity less that certain lvl

    # sorted_chunks = [x for _, x in sorted(zip(similarities, all_chunks), reverse=True)]

    sorted_chunks = [x for sim, x in sorted(zip(similarities, all_chunks), reverse=True) if sim > target_similarity]

    # Combine top 3 chunks for context

    top_chunks = sorted_chunks[:min(top_no, len(similarities))]
    combined_answer = " ".join(top_chunks)

    # print(combined_answer)

    return {"answer": combined_answer}




# message = "whats Serial Number - Service Tag for Manufacture: Juniper, Part Number: MX10003 and Hostname: AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-DCGW01"

# message = "whats Serial Number for Manufacture: Juniper, Part Number: MX10003 and Hostname: AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-DCGW01"

# message = "whats Serial Number - Service Tag for Manufacture: Juniper, Part Number: MX10003 and Hostname: AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-DCGW02"

# message = "whats Serial Number - Service Tag for Manufacture: Juniper, Part Number: EX4300-48T and Hostname: AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-MGT03"

message = "whats Serial Number - Service Tag for Manufacture: Juniper, Part Number: QFX5200-32C and Hostname: AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-LFSW04"


# message = "whats SFP Serial Number for Parent Device: AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-LFSW05, Part Number: 0/0/0:4,1,2,3 and SFP Part Number: QSFP28-100G-AOC-3M"

# message = "for Uplinks what is End User Junction Fiber/Port-B for End User Local ODF details-B: 2E ODF RK 3/SH7/F-9,10 and End User Port No-B: 1/0/5 and End User Node Name-B: AUH-A2E5-HSPER01 and Service-B:SPE End User Short Node: JUNIPER-NFVI2-CGW01"

# context = "<html><body><table><tr><td>Manufacture</td><td>Part Number</td><td>Hostname</td><td>Serial Number - Service Tag</td></tr><tr><td>Juniper</td><td>MX10003</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-DCGW01</td><td>JN1262C94JCB</td></tr><tr><td>Juniper</td><td>MX10003</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-DCGW02</td><td>JN1261906JCB</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-SPSW01</td><td>WH0218080408</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-SPSW02</td><td>WH0218080358</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-LFSW01</td><td>WH0218080230</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-LFSW02</td><td>WH0218080394</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-LFSW03</td><td>WH0218080287</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-LFSW04</td><td>WH0218080416</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-LFSW05</td><td>WH0218080378</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-LFSW06</td><td>WH0218080340</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-LFSW07</td><td>WH0218080407</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-LFSW08</td><td>WH0218080343</td></tr><tr><td>Juniper</td><td>QFX5100-48S</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-MGT01</td><td>TA3717320213</td></tr><tr><td>Juniper</td><td>QFX5100-48S</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-MGT02</td><td>TA3717320127</td></tr><tr><td>Juniper</td><td>EX4300-48T</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-MGT03</td><td>PE3718020143</td></tr><tr><td>Juniper</td><td>EX4300-48T</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-MGT04</td><td>PE3718020635</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-JMP01</td><td>209M3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-CNTRL01</td><td>20YQ3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-UNDRCLD01</td><td>228M3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-CEPH01</td><td>204M3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-SDN01</td><td>HX4S3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-CNTRL02</td><td>205L3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-UNDRCLD02</td><td>223T3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-CEPH02</td><td>204S3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-SDN02</td><td>HX5K3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-CNTRL03</td><td>210N3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-CEPH03</td><td>210P3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-SDN03</td><td>HX4T3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP09</td><td>205Q3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP08</td><td>206M3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP07</td><td>20FL3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP06</td><td>20JK3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP05</td><td>20HK3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP04</td><td>20GQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP03</td><td>20FQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP02</td><td>20DQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP01</td><td>204P3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-CEPH06</td><td>20YS3N2</td></tr></table></body></html>"

context = """<html><body><table><tr><td>Manufacture</td><td>Part Number</td><td>Hostname</td><td>Serial Number - Service Tag</td></tr><tr><td>Juniper</td><td>MX10003</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-DCGW01</td><td>JN1262C94JCB</td></tr><tr><td>Juniper</td><td>MX10003</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-DCGW02</td><td>JN1261906JCB</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-SPSW01</td><td>WH0218080408</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-SPSW02</td><td>WH0218080358</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-LFSW01</td><td>WH0218080230</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-LFSW02</td><td>WH0218080394</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-LFSW03</td><td>WH0218080287</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-LFSW04</td><td>WH0218080416</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-LFSW05</td><td>WH0218080378</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-LFSW06</td><td>WH0218080340</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-LFSW07</td><td>WH0218080407</td></tr><tr><td>Juniper</td><td>QFX5200-32C</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-LFSW08</td><td>WH0218080343</td></tr><tr><td>Juniper</td><td>QFX5100-48S</td><td>AUH-A2E07-NEC-NFVI2-RK01-JUNIPER-MGT01</td><td>TA3717320213</td></tr><tr><td>Juniper</td><td>QFX5100-48S</td><td>AUH-A2E07-NEC-NFVI2-RK02-JUNIPER-MGT02</td><td>TA3717320127</td></tr><tr><td>Juniper</td><td>EX4300-48T</td><td>AUH-A2E07-NEC-NFVI2-RK03-JUNIPER-MGT03</td><td>PE3718020143</td></tr><tr><td>Juniper</td><td>EX4300-48T</td><td>AUH-A2E07-NEC-NFVI2-RK04-JUNIPER-MGT04</td><td>PE3718020635</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-JMP01</td><td>209M3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-CNTRL01</td><td>20YQ3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-UNDRCLD01</td><td>228M3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-CEPH01</td><td>204M3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK01-DELL-SDN01</td><td>HX4S3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-CNTRL02</td><td>205L3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-UNDRCLD02</td><td>223T3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-CEPH02</td><td>204S3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK02-DELL-SDN02</td><td>HX5K3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-CNTRL03</td><td>210N3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-CEPH03</td><td>210P3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-SDN03</td><td>HX4T3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP09</td><td>205Q3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP08</td><td>206M3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP07</td><td>20FL3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP06</td><td>20JK3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP05</td><td>20HK3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP04</td><td>20GQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP03</td><td>20FQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP02</td><td>20DQ3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK03-DELL-COMP01</td><td>204P3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-CEPH06</td><td>20YS3N2</td></tr></table></body></html>

# $^\copyright$ 2018 NetCracker Technology Corporation NEC/Netcracker Confidential and Proprietary Disclose and distribute solely to those individuals with a need to know.

# <html><body><table><tr><td>etisalat</td><td>EtisalatNFVI2-SiteInstallationDocument(AUH-A2E07- NEC-NFVI2)</td><td>NEC Netcracker</td></tr></table></body></html>

# <html><body><table><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-CEPH05</td><td>20YM3N2</td></tr><tr><td>DELL</td><td>R740xd</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-CEPH04</td><td>211K3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-ELK04</td><td>20GT3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-ELK03</td><td>20FT3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-ELK02</td><td>20FN3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-ELK01</td><td>20GP3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-FCAP04</td><td>229K3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-FCAP03</td><td>225Q3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-FCAP02</td><td>224S3N2</td></tr><tr><td>DELL</td><td>R640</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-FCAP01</td><td>226M3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-MANO03</td><td>209K3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-MANO02</td><td>207K3N2</td></tr><tr><td>DELL</td><td>R740</td><td>AUH-A2E07-NEC-NFVI2-RK04-DELL-MANO01</td><td>204R3N2</td></tr></table></body></html>  """



embedding_model_name = "all-mpnet-base-v2"
# embedding_model_name = "all-MiniLM-L6-v2"
embedding_model = SentenceTransformer(embedding_model_name)
chroma_db_path = "chroma_db"
client = chromadb.PersistentClient(path=chroma_db_path)
collection = client.get_or_create_collection(name="file_chunks")

search_results = search_and_answer(message)
# context = search_results["answer"]

model, tokenizer = load_model("llama_8B_Instruct")
reply = invoke_llama(model, tokenizer, message, context)
print(reply)
