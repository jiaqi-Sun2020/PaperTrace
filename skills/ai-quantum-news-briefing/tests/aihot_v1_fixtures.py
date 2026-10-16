import json
def v1_response(payload):
    return json.dumps({'schemaVersion':1,'query':{'mode':'selected','window':'7d','by':'published','category':None,'q':None},
                       'items':payload['items'],'page':{'count':len(payload['items']),
                       'hasMore':payload.get('hasNext',False),'nextCursor':payload.get('nextCursor')}})
