# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 01:37:44 2019

@author: shuva
"""

import numpy as np
import tensorflow as tf
import re
import time


##############  N L P  ####################


lines=open("movie_lines.txt",encoding="utf-8",errors="ignore").read().split("\n")
conversations=open("movie_conversations.txt",encoding="utf-8",errors="ignore").read().split("\n")

id2Line={}
for line in lines:
    _line=line.split(" +++$+++ ")
    if len(_line)==5:
        id2Line[_line[0]]=_line[4]
        
conversation_ids=[]
for conversation in conversations[:-1]:
    _conv_id=conversation.split(" +++$+++ ")[-1][1:-1].replace("'","").replace(" ","").split(",")
    conversation_ids.append(_conv_id)
    

questions=[]
answers=[]
for conversation_id in conversation_ids:
    for i in range(len(conversation_id)-1):
        questions.append(id2Line[conversation_id[i]])
        answers.append(id2Line[conversation_id[i+1]])
        
def clean_text(text):
    text=text.lower()
    text=re.sub(r"i'm","i am",text)
    text=re.sub(r"she's","she is",text)
    text=re.sub(r"he's","he is",text)
    text=re.sub(r"it's","it is",text)
    text=re.sub(r"that's","that is",text)
    text=re.sub(r"what's","what is",text)
    text=re.sub(r"there's","there is",text)
    text=re.sub(r"where's","where is",text)
    text=re.sub(r"\'ve"," have",text)
    text=re.sub(r"\'ll"," will",text)
    text=re.sub(r"\'re"," are",text)
    text=re.sub(r"\'d"," would",text)
    text=re.sub(r"let's","let us",text)
    text=re.sub(r"wasn't","was not",text)
    text=re.sub(r"won't","would not",text)
    text=re.sub(r"shan't","should not",text)
    text=re.sub(r"can't","cannot",text)
    text=re.sub(r"don't","do not",text)
    text=re.sub(r"aren't","are not",text)
    text=re.sub(r"couldn't","could not",text)
    text=re.sub(r"didn't","did not",text)
    text=re.sub(r"doesn't","dows not",text)
    text=re.sub(r"hasn't","has not",text)
    text=re.sub(r"hadn't","had not",text)
    text=re.sub(r"haven't","have not",text)
    text=re.sub(r"isn't","is not",text)
    text=re.sub(r"mustn't","must not",text)
    text=re.sub(r"[~@!.#$%*?\"(){};:,|=-]","",text)
    return text


clean_questions=[]
clean_answers=[]
for question in questions:
    clean_questions.append(clean_text(question))
    
for answer in answers:
    clean_answers.append(clean_text(answer))
    

wordcount={}
for question in clean_questions:
    for word in question.split():
        if word not in wordcount:
            wordcount[word]=1
        else:
            wordcount[word]+=1
            
for answer in clean_answers:
    for word in answer.split():
        if word not in wordcount:
            wordcount[word]=1
        else:
            wordcount[word]+=1

questionwords2int={}
threshold=20
word_no=0
for word,count in wordcount.items():
    if count>=threshold:
        questionwords2int[word]=word_no
        word_no+=1

answerwords2int={}
word_no=0
for word,count in wordcount.items():
    if count>=threshold:
        answerwords2int[word]=word_no
        word_no+=1
        
tokens=["<PAD>","<EOS>","<OUT>","<SOS>"]
for token in tokens:
    questionwords2int[token]=len(questionwords2int)+1

for token in tokens:
    answerwords2int[token]=len(answerwords2int)+1
    
    
answerint2words={i:w for w,i in answerwords2int.items()}

for i in range(len(clean_answers)):
    clean_answers[i]+=" <EOS>"

questions2int=[]
for question in clean_questions:
    ints=[]
    for word in question.split():
        if word not in questionwords2int:
            ints.append(questionwords2int["<OUT>"])
        else:
            ints.append(questionwords2int[word])
    questions2int.append(ints)

answers2int=[]
for answer in clean_answers:
    ints=[]
    for word in answer.split():
        if word not in answerwords2int:
            ints.append(answerwords2int["<OUT>"])
        else:
            ints.append(answerwords2int[word])
    answers2int.append(ints)
    
sorted_clean_questions=[]
sorted_clean_answers=[]
for length in range (1,26):
    for i in enumerate(questions2int):
        if len(i[1])==length:
            sorted_clean_questions.append(questions2int[i[0]])
            sorted_clean_answers.append(answers2int[i[0]])
            
            
            
##############  BUilding Seq2seq Model   ###################


def model_inputs():
    inputs=tf.placeholder(tf.int32,[None,None],name="inputs")
    target=tf.placeholder(tf.int32,[None,None],name="target")
    lr=tf.placeholder(tf.float32,name="learning_rate")
    keep_prob=tf.placeholder(tf.float32,name="keep_prob")
    return inputs,target,lr,keep_prob




def preprocess_targets(targets,word2int,batch_size):
    left_side=tf.fill([batch_size,1],word2int["<SOS>"])
    right_side=tf.strided_slice(targets,[0,0],[batch_size,-1],[1,1])
    preprocessed_targets=tf.concat([left_side,right_side],1)
    return preprocessed_targets



#Creating encoder
    
def encoder_rnn_layer(rnn_inputs, rnn_size, num_layers, keep_prob, sequence_length):
    lstm = tf.contrib.rnn.BasicLSTMCell(rnn_size)
    lstm_dropout = tf.contrib.rnn.DropoutWrapper(lstm, input_keep_prob = keep_prob)
    encoder_cell = tf.contrib.rnn.MultiRNNCell([lstm_dropout] * num_layers)
    _, encoder_state = tf.nn.bidirectional_dynamic_rnn(cell_fw = encoder_cell,
                                                       cell_bw = encoder_cell,
                                                       sequence_length = sequence_length,
                                                       inputs = rnn_inputs,
                                                       dtype = tf.float32)
    return encoder_state





def decode_training_set(encoder_state, decoder_cell, decoder_embedded_input, sequence_length, decoding_scope, output_function, keep_prob, batch_size):
    attention_states = tf.zeros([batch_size, 1, decoder_cell.output_size])
    attention_keys, attention_values, attention_score_function, attention_construct_function = tf.contrib.seq2seq.prepare_attention(attention_states, attention_option = "bahdanau", num_units = decoder_cell.output_size)
    training_decoder_function = tf.contrib.seq2seq.attention_decoder_fn_train(encoder_state[0],
                                                                              attention_keys,
                                                                              attention_values,
                                                                              attention_score_function,
                                                                              attention_construct_function,
                                                                              name = "attn_dec_train")
    decoder_output, decoder_final_state, decoder_final_context_state = tf.contrib.seq2seq.dynamic_rnn_decoder(decoder_cell,
                                                                                                              training_decoder_function,
                                                                                                              decoder_embedded_input,
                                                                                                              sequence_length,
                                                                                                              scope = decoding_scope)
    decoder_output_dropout = tf.nn.dropout(decoder_output, keep_prob)
    return output_function(decoder_output_dropout)




def decode_test_set(encoder_state, decoder_cell, decoder_embeddings_matrix, sos_id, eos_id, maximum_length, num_words, decoding_scope, output_function, keep_prob, batch_size):
    attention_states = tf.zeros([batch_size, 1, decoder_cell.output_size])
    attention_keys, attention_values, attention_score_function, attention_construct_function = tf.contrib.seq2seq.prepare_attention(attention_states, attention_option = "bahdanau", num_units = decoder_cell.output_size)
    test_decoder_function = tf.contrib.seq2seq.attention_decoder_fn_inference(output_function,
                                                                              encoder_state[0],
                                                                              attention_keys,
                                                                              attention_values,
                                                                              attention_score_function,
                                                                              attention_construct_function,
                                                                              decoder_embeddings_matrix,
                                                                              sos_id,
                                                                              eos_id,
                                                                              maximum_length,
                                                                              num_words,
                                                                              name = "attn_dec_inf")
    test_predictions, decoder_final_state, decoder_final_context_state = tf.contrib.seq2seq.dynamic_rnn_decoder(decoder_cell,
                                                                                                                test_decoder_function,
                                                                                                                scope = decoding_scope)
    return test_predictions




#creating_decoder
def decoder_rnn(decoder_embedded_input, decoder_embedding_matrix, encoder_state, num_words, sequence_length, rnn_size, num_layers, word2int, keep_prob, batch_size):
    with tf.variable_scope("decoding") as decoding_scope:
        lstm = tf.contrib.rnn.BasicLSTMCell(rnn_size)
        lstm_dropout = tf.contrib.rnn.DropoutWrapper(lstm, input_keep_prob = keep_prob)
        decoder_cell = tf.contrib.rnn.MultiRNNCell([lstm_dropout]*num_layers)
        weights = tf.truncated_normal_initializer(stddev = 0.1)
        biases = tf.zeros_initializer()
        output_function = lambda x: tf.contrib.layers.fully_connected(x,
                                                                      num_words,
                                                                      None,
                                                                      scope = decoding_scope,
                                                                      weights_initializer = weights,
                                                                      biases_initializer = biases)
        training_predictions = decode_training_set(encoder_state,
                                                   decoder_cell,
                                                   decoder_embedded_input,
                                                   sequence_length,
                                                   decoding_scope,
                                                   output_function,
                                                   keep_prob,
                                                   batch_size)
        decoding_scope.reuse_variables()
        test_predictions = decode_test_set(encoder_state,
                                         decoder_cell,
                                         decoder_embedding_matrix,
                                         word2int["<SOS>"],
                                         word2int["<EOS>"],
                                         sequence_length - 1,
                                         num_words,
                                         decoding_scope,
                                         output_function,
                                         keep_prob,
                                         batch_size)
      
    return training_predictions, test_predictions



#Building model
def seq2seq_model(inputs, targets, keep_prob, batch_size, sequence_length, answers_num_words, questions_num_words, encoder_embedding_size, decoder_embedding_size, rnn_size, num_layers, questionwords2int):
    encoder_embedded_input = tf.contrib.layers.embed_sequence(inputs,
                                                              answers_num_words + 1,
                                                              encoder_embedding_size,
                                                              initializer = tf.random_uniform_initializer(0,1))
    encoder_state = encoder_rnn_layer(encoder_embedded_input, rnn_size, num_layers, keep_prob, sequence_length)
    preprocessed_targets = preprocess_targets(targets, questionwords2int, batch_size)
    decoder_embedding_matrix = tf.Variable(tf.random_uniform([questions_num_words + 1, decoder_embedding_size], 0, 1))
    decoder_embedding_input  = tf.nn.embedding_lookup(decoder_embedding_matrix, preprocessed_targets)
    training_prediction, test_prediction = decoder_rnn(decoder_embedding_input,
                                                       decoder_embedding_matrix,
                                                       encoder_state,
                                                       questions_num_words,
                                                       sequence_length,
                                                       rnn_size,
                                                       num_layers,
                                                       questionwords2int,
                                                       keep_prob,
                                                       batch_size)
    return training_prediction, test_prediction




##################    Training the Model   ###################    
    

epochs = 100
batch_size = 64
rnn_size = 512
num_layers = 3
encoding_embedding_size = 512
decoding_embedding_size = 512
learning_rate = 0.01
learning_rate_decay = 0.9
min_learning_rate = 0.0001
keep_probability = 0.5



#opening a tff session for training
tf.reset_default_graph()
session = tf.InteractiveSession()


inputs, targets, lr, keep_prob = model_inputs()

sequence_length = tf.placeholder_with_default(25, None, name = "sequence_length")

input_shape = tf.shape(inputs)

training_predictions, test_predictions = seq2seq_model(tf.reverse(inputs, [-1]),
                                                                  targets,
                                                                  keep_prob,
                                                                  batch_size,
                                                                  sequence_length,
                                                                  len(answerwords2int),
                                                                  len(questionwords2int),
                                                                  encoding_embedding_size,
                                                                  decoding_embedding_size,
                                                                  rnn_size,
                                                                  num_layers,
                                                                  questionwords2int)



with tf.name_scope("optimization"):
    loss_error = tf.contrib.seq2seq.sequence_loss(training_predictions,
                                                  targets,
                                                  tf.ones([input_shape[0], sequence_length]))
    optimizer = tf.train.AdamOptimizer(learning_rate)
    gradients = optimizer.compute_gradients(loss_error)
    clipped_gradients = [(tf.clip_by_value(grad_tensor, -5., 5.), grad_variable) for grad_tensor, grad_variable in gradients if grad_tensor is not None]
    optimizer_gradient_clipping = optimizer.apply_gradients(clipped_gradients)
    

def apply_padding(batch_of_sequences, word2int):
    max_sequence_length = max([len(sequence) for sequence in batch_of_sequences])
    return [sequence + [word2int["<PAD>"]] * (max_sequence_length - len(sequence)) for sequence in batch_of_sequences]


def split_into_batches(questions, answers, batch_size):
    for batch_index in range(0, len(questions) // batch_size):
        start_index = batch_index * batch_size
        questions_in_batch = questions[start_index : start_index + batch_size]
        answers_in_batch = answers[start_index : start_index + batch_size]
        padded_questions_in_batch = np.array(apply_padding(questions_in_batch, questionwords2int))
        padded_answers_in_batch = np.array(apply_padding(answers_in_batch, answerwords2int))
        yield padded_questions_in_batch, padded_answers_in_batch


training_validation_split = int(len(sorted_clean_questions) * 0.15)
training_questions = sorted_clean_questions[training_validation_split : ]
training_answers = sorted_clean_answers[training_validation_split : ]
validation_questions = sorted_clean_questions[:training_validation_split]
validation_answers = sorted_clean_answers[:training_validation_split]  



#Training
batch_index_check_training_loss = 100
batch_index_check_validation_loss = ((len(training_questions))//batch_size // 2) - 1
total_training_loss_error = 0
list_validation_loss_error = []
early_stopping_check = 0
early_stopping_stop = 1000
checkpoint = "./chatbot_weights.ckpt"
session.run(tf.global_variables_initializer())
for epoch in range(1, epochs + 1):
    for batch_index, (padded_questions_in_batch, padded_answers_in_batch) in enumerate(split_into_batches(training_questions, training_answers, batch_size)):
        starting_time = time.time()
        _, batch_training_loss_error = session.run([optimizer_gradient_clipping, loss_error], {inputs: padded_questions_in_batch,
                                                   targets: padded_answers_in_batch,
                                                   lr: learning_rate,
                                                   sequence_length: padded_answers_in_batch.shape[1],
                                                   keep_prob: keep_probability})
        total_training_loss_error += batch_training_loss_error
        ending_time = time.time()
        batch_time = ending_time - starting_time
        if batch_index % batch_index_check_training_loss == 0:
            print("Epoch: {:>3}/{}, Batch: {:>4}/{}, Training Loss Error: {:>6.3f}, Training Time on 100 Batches: {:d} seconds".format(epoch,
                  epochs,
                  batch_index,
                  len(training_questions) // batch_size,
                  total_training_loss_error / batch_index_check_training_loss,
                  int(batch_time * batch_index_check_training_loss)))
            total_training_loss_error = 0
        if batch_index % batch_index_check_validation_loss == 0 and batch_index >0:
            total_validation_loss_error = 0
            starting_time = time.time()
            for batch_index_validation, (padded_questions_in_batch, padded_answers_in_batch) in enumerate(split_into_batches(validation_questions, validation_answers, batch_size)):
    
                batch_validation_loss_error = session.run(loss_error, {inputs: padded_questions_in_batch,
                                                   targets: padded_answers_in_batch,
                                                   lr: learning_rate,
                                                   sequence_length: padded_answers_in_batch.shape[1],
                                                   keep_prob : 1})
                total_validation_loss_error += batch_validation_loss_error
            ending_time = time.time()
            batch_time = ending_time - starting_time
            average_validation_loss_error = total_validation_loss_error / (len(validation_questions) / batch_size)
            print("Validation Loss Error: {:>6.3f}, Batch Validation Time: {:d} seconds".format(average_validation_loss_error, int(batch_time)))
            
            learning_rate *= learning_rate_decay
            if learning_rate < min_learning_rate:
                learning_rate = min_learning_rate
            list_validation_loss_error.append(average_validation_loss_error)
            if average_validation_loss_error <= min(list_validation_loss_error):
                print("I speak better now!!!")
                early_stopping_check = 0
                saver = tf.train.Saver()
                saver.save(session, checkpoint)
            else:
                print("Sorry I do not speak better, I need to practice more")
                early_stopping_check +=1
                if early_stopping_check == early_stopping_stop:
                    break
    if early_stopping_check == early_stopping_stop:
        print("Sorry! I can't speak better than this anymore")
        break
print("Game Over")



############  Loading the training data  ###############
checkpoint = "./chatbot_weights.ckpt"
session = tf.InteractiveSession()
session.run(tf.global_variables_initializer())
saver = tf.train.Saver()
saver.restore(session, checkpoint)



def convert_string2int(question, word2int):
    question.clean_text(question)
    return [word2int.get(word, word2int["<OUT>"]) for word in question.split()]


#setting_up_chat
    
while(True):
    question = input("You: ")
    if question == "Goodbye":
        break
    question = convert_string2int(question, questionwords2int)
    question = question + [questionwords2int["<PAD>"]] * (20- len(question))
    fake_batch = np.zeros((batch_size, 20))
    fake_batch[0] = question
    predicted_answer = session.run(test_predictions, {inputs: fake_batch, keep_prob: 0.5})[0]
    answer = ""
    for i in np.argmax(predicted_answer, 1):
        if answerint2words[i] == "i":
            token = "I"
        elif answerint2words[i] == "<OUT>":
            token = "out"
        else:
            token = " "+answerint2words[i]
        answer += token
        if token == ".":
            break
    print("ChatBot: "+ answer)