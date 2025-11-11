'''import pandas as pd, pymongo, os
from dotenv import load_dotenv
from mlxtend.frequent_patterns import apriori, association_rules

load_dotenv()
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB","skilllens")]

docs = list(db.candidates.find({}, {"skills": 1}))
df = pd.DataFrame(docs)
skills_set = set(s for row in df.skills.dropna() for s in row)
onehot = pd.DataFrame([{s: (s in (row or [])) for s in skills_set} for row in df.skills])

freq = apriori(onehot, min_support=0.1, use_colnames=True)
rules = association_rules(freq, metric="lift", min_threshold=1.0)
print(rules.head())
'''