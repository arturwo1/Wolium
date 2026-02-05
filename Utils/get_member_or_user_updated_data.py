from nextcord import Member

def deep_compare(before, after, path=""):
  changes = {}

  # print("before: ", before, "\nafter: ", after, "\npath: ", path)

  if not before or not after:
    return changes

   
  if isinstance(before, list) and isinstance(after, list): 
    before_set = set(before)
    after_set = set(after)

    added = after_set - before_set
    removed = before_set - after_set

    # print(f"added_set_{path}:",added)
    # print(f"removed_set_{path}:",removed)

    # if added:
    #   changes.append(f"**{path} добавлено:** {', '.join(map(str, added))}")
    #   changes["path_added"] = ', '.join(map(str, added))
    # if removed:
    #   changes.append(f"**{path} удалено:** {', '.join(map(str, removed))}")
    changes = {path:{f'{path}_added': added, f'{path}_deleted': removed}}
  elif isinstance(before, dict) and isinstance(after, dict): 
    changes = {
      key: {
        f'{key}_before': before[key],
        f'{key}_after': after[key]
      }
      for key in before if key in after and before[key]!=after[key]
    }
  else: 
    if before != after:
      changes[path]={
        f'{path}_before': before,
        f'{path}_after': after
      }
  # print("path: ",path)
  # print("changes_before: ",before)
  # print("changes_after: ",after)
  # print("changes: ",changes)
  return changes

def object_to_dict(obj,depth=3):
  if depth<=0 or obj==None:
    return obj
  if not obj:
    return None
  # print("\nobj: ",obj,"\n")
  if isinstance(obj,(str,int,float,bool,type(None))):
    return obj
  if isinstance(obj,Member):
    return {
      "name": obj.name,
      "global_name": obj.global_name,
      "display_name": obj.display_name,
      "nick": obj.nick,
      "roles": [{data.name:F'<@&{data.id}>'} for data in obj.roles],
      "timeout": obj._timeout.second if obj._timeout else None,
      "status": obj.status,
      "activity": [{
        "name":activity.name,
        "type":str(activity.type.name) if activity.type else None
        } for activity in obj.activities]
    }
  # if isinstance(obj, list):
  #   print('list',obj)
  #   return [object_to_dict(i,depth-1) for i in obj]
  # if isinstance(obj, dict):
  #   print('dict',obj)
  #   return {k: object_to_dict(v,depth-1) for k, v in obj.items()}
  attributes={}
  if hasattr(obj, '__slots__'):
    # print('slots',obj)
    for attr in obj.__slots__:
      if attr.startswith("_") and attr not in ['_timeout','_banner','_avatar','_state','_client_status','_roles'] or attr in ['emojis','stickers','features']:
        continue
      # print("attr:", attr, "\nobj:", obj)
      try:
        value = getattr(obj,attr)
        # print("value:", value)
        attributes[attr]=object_to_dict(value,depth-1)
        # print("depth:",depth)
      except Exception as e:
        attributes[attr]=f"Error: {e}"
    # print("attributes:",attributes)
    return attributes
  # for attr in dir(obj):
  #   if attr.startswith("__"):
  #     continue
  #   try:
  #     value = getattr(obj,attr)
  #     attributes[attr]=object_to_dict(value,depth-1)
  #   except Exception as e:
  #     attributes[attr]=f"Error: {e}"
  # return attributes
  return obj
  
# print(vars(nextcord.Member))