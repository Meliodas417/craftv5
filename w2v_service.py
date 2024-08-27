from flask import Flask, request
from flask_restful import Api, Resource
import os
import gensim
import pickle
from nltk import word_tokenize
import numpy as np

# 手动指定training dataset路径
training_dataset = 'googleplay.txt'

# 加载训练集数据
def load_trainingset(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = file.readlines()
    return [line.strip() for line in data]

# 加载 Word2Vec 模型
model_path_w2v = os.path.join(os.getcwd(), 'GoogleNews-vectors-negative300.bin')
model_w2v = gensim.models.KeyedVectors.load_word2vec_format(model_path_w2v, binary=True)

# 缓存相似度计算结果
cached_sim = dict()
pkl_path = "./w2v_sim_cache.pkl"

if os.path.exists(pkl_path):
    with open(pkl_path, 'rb') as f:
        cached_sim = pickle.load(f)

# 训练集数据
training_data = load_trainingset(training_dataset)

def w2v_sim(w_from, w_to):
    if (w_from, w_to) in cached_sim:
        return cached_sim[(w_from, w_to)]
    elif (w_to, w_from) in cached_sim:
        return cached_sim[(w_to, w_from)]
    else:
        if w_from.lower() == w_to.lower():
            sim = 1.0
        elif w_from in model_w2v.key_to_index and w_to in model_w2v.key_to_index:
            sim = 1 / (1 + model_w2v.wmdistance(word_tokenize(w_from), word_tokenize(w_to)))
        else:
            sim = None
        cached_sim[(w_from, w_to)] = sim
        with open(pkl_path, 'wb') as f:
            pickle.dump(cached_sim, f)
        return sim

def w2v_sent_sim(s_new, s_old):
    scores = []
    valid_new_words = set()
    valid_old_words = set(s_old)
    for w1 in s_new:
        for w2 in valid_old_words:
            sim = w2v_sim(w1, w2)
            if sim:
                valid_new_words.add(w1)
                scores.append((w1, w2, sim))
    scores = sorted(scores, key=lambda x: x[2], reverse=True)
    counted = []
    for new_word, old_word, score in scores:
        if new_word in valid_new_words and old_word in valid_old_words:
            valid_new_words.remove(new_word)
            valid_old_words.remove(old_word)
            counted.append(score)
        if not valid_new_words or not valid_old_words:
            break
    return sum(counted) / len(counted) if counted else None

class WordSim(Resource):
    def get(self):
        return {'error': 'Non-supported HTTP Method'}, 200

    def post(self):
        args = request.json
        sent_sim = w2v_sent_sim(args['s_new'], args['s_old'])
        return {'sent_sim': sent_sim}, 200


    def put(self):
        return {'error': 'Non-supported HTTP Method'}, 200

    def delete(self):
        return {'error': 'Non-supported HTTP Method'}, 200

if __name__ == '__main__':
    app = Flask(__name__)
    api = Api(app)
    api.add_resource(WordSim, '/w2v')
    app.run(debug=True)
