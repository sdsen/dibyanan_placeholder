# from llamafactory.chat import ChatModel
# from llamafactory.extras.misc import torch_gc



# args = dict(
#   model_name_or_path="deepseek-ai/deepseek-coder-1.3b-base", # use bnb-4bit-quantized Llama-3-8B-Instruct model
#   adapter_name_or_path="/cos_mount/users/dibyanayan/deepseek_lora_ept", 
#   template="empty",# load the saved LoRA adapters                     # same to the one in training
#   finetuning_type="lora",                  # same to the one in training
#   quantization_bit=4,                    # load 4-bit quantized model
# )
# chat_model = ChatModel(args)

# messages = []
# print("Welcome to the CLI application, use `clear` to remove the history, use `exit` to exit the application.")

# query = "\n\n def foo():   a = bar()\n   return a"


# messages = []
# messages.append({"role": "user", "content": query})

# print('response')
# for new_text in chat_model.stream_chat(messages):
#     print(new_text, end="", flush=True)

# torch_gc()

import argparse

parser = argparse.ArgumentParser(description='Process some integers.')

parser.add_argument('--ept')

args = parser.parse_args()


import json



from datasets import load_dataset

dataset = load_dataset("tianyang/repobench_python_v1.1")

import re

def construct_prompt(
    data: dict,
    language: str = "python",
    tokenizer= None,
    max_token_nums: int = 15800
    ) -> str:
    """
    Construct the prompt for next line prediction.

    :param data: data point from the dataset
    :param language: the language of the code
    :param tokenizer: the tokenizer of the evaluation model
    :param max_token_nums: the maximum number of tokens constraint for the prompt

    :return: the constructed prompt
    """

    # comment symbol for different languages
    comment_symbol = "#" if language == "python" else "//"

    # construct the cross-file prompt and in-file prompt separately
    # cross-file prompt
    cross_file_prompt = f"{comment_symbol} Repo Name: {data['repo_name']}\n"

    for snippet in data['context']:
        cross_file_prompt += f"{comment_symbol} Path: {snippet['path']}\n{snippet['snippet']}" + "\n\n"

    # in-file prompt
    in_file_prompt = f"{comment_symbol} Path: {data['file_path']}\n{data['import_statement']}\n{data['cropped_code']}\n"

    #in_file_prompt = f"{comment_symbol} Path: {data['file_path']}\n{data['cropped_code']}\n"

    # if we assign the tokenizer and the max_token_nums, we will truncate the cross-file prompt to meet the constraint
    if tokenizer is not None and max_token_nums is not None:

        cross_file_prompt_token_nums = len(tokenizer.encode(cross_file_prompt))
        in_file_prompt_token_nums = len(tokenizer.encode(in_file_prompt))

        exceed_token_nums = cross_file_prompt_token_nums + in_file_prompt_token_nums - max_token_nums

        if exceed_token_nums > 0:
            # split the cross-file prompt into lines
            cross_file_prompt_lines = cross_file_prompt.split("\n")
            # drop lines from end until the extra token number is less than 0
            for i in range(len(cross_file_prompt_lines)-1, -1, -1):
                exceed_token_nums -= len(tokenizer.encode(cross_file_prompt_lines[i]))
                if exceed_token_nums < 0:
                    break

            # join the lines back
            cross_file_prompt = "\n".join(cross_file_prompt_lines[:i]) + "\n\n"

    # combine the cross-file prompt and in-file prompt
    prompt = cross_file_prompt + in_file_prompt

    # normalize some empty lines
    prompt = re.sub(r'\n{4,}', '\n\n', prompt)

    return prompt


# define model and tokenizer

from transformers import AutoTokenizer, AutoModelForCausalLM

if int(args.ept)==1:
    print('using trained EPT model for inference')
    tokenizer = AutoTokenizer.from_pretrained("/cos_mount/users/dibyanayan/deepseek_full_ept")
    model = AutoModelForCausalLM.from_pretrained("/cos_mount/users/dibyanayan/deepseek_full_ept").to('cuda')
else:
    print('using original pretrained model for inference')
    tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/deepseek-coder-1.3b-base")
    model = AutoModelForCausalLM.from_pretrained("deepseek-ai/deepseek-coder-1.3b-base").to('cuda')


from fuzzywuzzy import fuzz

def exact_match_score(predictions, ground_truths):
    """
    This function computes the average exact match score between the predicted codes and the ground truth codes.
    It returns a float value between 0 and 1 indicating the degree of exact match between the predicted codes
    and the ground truth codes, where a value of 1 means all the predicted codes exactly match their corresponding
    ground truth codes and a value of 0 means none of the predicted codes exactly match their corresponding
    ground truth codes.

    Args:
    predictions: list, predicted codes
    ground_truths: list, ground truth codes

    Returns:
    Float, the average exact match score between the predicted codes and the ground truth codes.
    """
    if len(predictions) != len(ground_truths):
        raise ValueError("The length of the predicted codes and the ground truth codes should be equal.")

    exact_match = 0
    for pred, gt in zip(predictions, ground_truths):
        if pred.split() == gt.split():
            exact_match += 1

    return round(exact_match / len(predictions), 5)




def edit_similarity_score(predictions, ground_truths):
    """
    This function computes the average edit similarity score between the predicted codes and the ground truth codes.
    It returns a float value between 0 and 1 indicating the degree of similarity between the predicted codes
    and the ground truth codes, where a value of 1 means all the predicted codes are identical to their corresponding
    ground truth codes and a value of 0 means none of the predicted codes are similar to their corresponding
    ground truth codes.

    Args:
    predictions: list, predicted codes
    ground_truths: list, ground truth codes

    Returns:
    Float, the average edit similarity score between the predicted codes and the ground truth codes.
    """
    if len(predictions) != len(ground_truths):
        raise ValueError("The length of the predicted codes and the ground truth codes should be equal.")

    edit_sim = 0.0
    for pred, gt in zip(predictions, ground_truths):
        edit_sim += fuzz.ratio(pred, gt)

    return round(edit_sim / len(predictions), 5)



P = []
G = []

kk = len(dataset)
print(kk)
import pandas as pd
df = {'prompt': [], 'pred': [], 'act': []}
from tqdm import tqdm

for prompt_no in tqdm(range(100)):
  # print(dataset['cross_file_first'][prompt_no]['token_num'])
  # print(0/0)
  if dataset['cross_file_first'][prompt_no]['token_num']<2000: 
    prompt = construct_prompt(dataset['cross_file_first'][prompt_no], tokenizer=tokenizer, max_token_nums=2000)
    # if prompt_no==2:
    #     print(prompt)
    # ls = prompt.split("\n")
    # lst = [f' {x}' for x in ls]
    # prompt = "\n".join(lst)
    # if prompt_no==2:
    #     print(prompt)
    tokenizer.pad_token_id = tokenizer.eos_token_id
    inputs = tokenizer([prompt], return_tensors="pt")

    # Example 1: Print the scores for each token generated with Greedy Search
    # outputs = model.generate(input_ids = inputs['input_ids'].to('cuda'), attention_mask = inputs['attention_mask'].to('cuda'), max_new_tokens=128, return_dict_in_generate=True, output_scores=True, eos_token_id=tokenizer.encode("\n")[0])
    
    outputs = model.generate(input_ids = inputs['input_ids'].to('cuda'), attention_mask = inputs['attention_mask'].to('cuda'), max_new_tokens=128, return_dict_in_generate=True, output_scores=True)
      
    transition_scores = model.compute_transition_scores(
      outputs.sequences, outputs.scores, normalize_logits=True
    )


    pred = tokenizer.batch_decode(outputs.sequences[:,inputs['input_ids'].shape[1]:])[0].split("\n")[0]
    act = dataset['cross_file_first'][prompt_no]['next_line']

    df['pred'].append(pred)
    df['act'].append(act)
    df['prompt'].append(prompt)
    P.append(pred)
    G.append(act)
    print(f"Predicted: {pred}")
    print(f"Actual: {act}")

import evaluate
perplexity = evaluate.load("perplexity", module_type="metric")
df = pd.DataFrame(df)
all_pt = []
for _, row in df.iterrows():
    tot = str(row['prompt']) + '\n' + str(row['pred'])
    all_pt.append(tot)
results = perplexity.compute(model_id='microsoft/phi-2',
                             add_start_token=False,
                             predictions=all_pt)

lop = results['perplexities']
final_df = pd.DataFrame({'prompt': list(df['prompt']), 'pred': list(df['pred']), 
            'act': list(df['act']), 'ppl': lop})


if int(args.ept)==1:
    final_df.to_csv('/cos_mount/users/dibyanayan/df_ept_infer.csv')
else:
    final_df.to_csv('/cos_mount/users/dibyanayan/df_normal_infer.csv')
    

print(exact_match_score(P,G))
print(edit_similarity_score(P,G))
