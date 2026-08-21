import sys
import traceback

try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print('sentence-transformers import and model load: OK')
    print('Model device:', model.device)
    # Quick encode test
    vec = model.encode('test query')
    print('Quick encode OK, vector shape:', vec.shape)
except Exception as e:
    print('FAILED')
    traceback.print_exc()