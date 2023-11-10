#!/usr/bin/env python

import os
import re
import json
import requests
import jsondiff as jd
from jsondiff import diff
import traceback
import shutil
import tempfile



USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36"
PUSHOVER_API_TOKEN = os.environ['PUSHOVER_API_TOKEN']
PUSHOVER_USER_KEY = os.environ['PUSHOVER_USER_KEY']

patchwerks_urls = [
  {
    'url': "https://patchwerks.com/collections/used",
    'data_file': 'collection-used.json',
    'title': 'Patchwerks Used'
  },
#  {
#    'url': 'https://patchwerks.com/collections/restocks',
#    'data_file': 'collections-restocks.json',
#    'title': 'Patchwerks Restock'
#  },
#  {
#    'url': 'https://patchwerks.com/collections/new-products-new-to-patchwerks',
#    'data_file': 'collections-new-products-new-to-patchwerks.json',
#    'title': 'Patchwerks New'
#  }
]


# def download_thumbnail( session, url ):
#   r = session.get( url, stream=True)
#   if r.status_code == 200:
#       with tempfile.NamedTemporaryFile(delete=False) as tmp:
#           for chunk in r.iter_content(1024):
#               tmp.write(chunk)
#           return tmp.name
#   
#   return None


def format_row( row, page_url=None, changes=None ):
  return "Name: {name} {price} ({sku})".format( 
    name = row['title'], 
    price = row['offers'][0]['price'], 
    sku = row['offers'][0]['sku']
  )

def get_diff_report( diff, prev, new, page, session ):
  report = ''
  
  # New things
  if jd.insert in diff:
    for (position,row) in diff[jd.insert]:
      report += "ADDED: " + format_row( row ) + "\n"
            
      send_notification(
        "ADDED: {page}".format(page=page['title']), 
        format_row(row), 
        page['url'] + '/products/' + row['product_id'], 
        "https:{path}" .format(path=row['thumbnail_url'])
      )

      
      
      
  #  
  # Changed things
  #
  for key,changes in diff.items():
    
    if key in [jd.insert,jd.delete]:
      continue

    c = new[key]    
    product_id = c['product_id']
    p = next((x for x in prev if x['product_id'] == product_id), None)
   
   # Look the product my id, if not found skip.  Since this should be changes only
   # this is a problem
    if( p == None ):
      continue 

    
    change_report = ' '
    if 'offers' in changes:
      for position,change in changes['offers'].items():
        if( position == jd.delete ):
          continue
        for field,value in change.items():
          
          change_report += "{field}: {old_value}->{new_value} ".format(
            field = field,
            old_value = p['offers'][position][field],
            new_value = c['offers'][position][field]
          )

    report += "CHANGED: " + format_row( c ) + change_report + "\n"
    
    send_notification(
      "CHANGED: {page}".format(page=page['title']), 
      format_row(c) + "\n" + change_report, 
      page['url'] + '/products/' + c['product_id'], 
      "https:{path}" .format(path=c['thumbnail_url'])
    )
    
  # Deleted things
  if jd.delete in diff:
    for position in diff[jd.delete]:
      row = prev[position]
      report += "DELETED: " + format_row( row ) + "\n"
    
      send_notification(
        "GONE: {page}".format(page=page['title']), 
        format_row(row), 
        page['url'] + '/products/' + row['product_id'], 
        "https:{path}" .format(path=row['thumbnail_url'])
      )
  
  return report

def send_notification( title, message, url, image_url=None ):
  
   
  # defining the api-endpoint
  API_ENDPOINT = "https://api.pushover.net/1/messages.json"


  data = {
    'token': PUSHOVER_API_TOKEN,
    'user': PUSHOVER_USER_KEY,
    'title': title,
    'message': message,
    'url': url
  }
  
  files = None
  
  if( image_url ):
    r = requests.get( image_url, stream=True)
    if r.status_code == 200:
      filename = ""
      with tempfile.NamedTemporaryFile() as tmp:
        for chunk in r.iter_content(1024):
          tmp.write(chunk)
        filename = tmp.name
        
        files = {
          "attachment": ("image.jpg", open(filename, "rb"), "image/jpeg")
        }
      
        print( url, filename, files)

        r = requests.post(
          "https://api.pushover.net/1/messages.json", 
          data = data,
          files = files
        )
      
  else:
  
    r = requests.post(
      "https://api.pushover.net/1/messages.json", 
      data = data,
    )
  







##
##
##
if __name__ == '__main__':
  aggregate_report = ""
  
  for page in patchwerks_urls:
    
    url = page['url']
    data_file = page['data_file']
    print(url)

    try:
      with open(data_file, 'r') as f:
        previous_product_data = json.load(f)
    except Exception as e:
      previous_product_data = None
      print( "Error loading previous data... soldiering on.")
      print(e)

    # initialize a session
    session = requests.Session()

    # set the User-agent as a regular browser
    session.headers["User-Agent"] = USER_AGENT
    
    # get the HTML content
    data_url = url + '.oembed'
    try:
      response = session.get(data_url, verify=False)
        
      if not response.ok:  
        aggregate_report += url + "\n\nError fetching data: " + str(response) +"\n"
      else:
        current_product_data = json.loads( response.content )
        current_product_data = current_product_data['products']
        
        d = diff( previous_product_data, current_product_data )
        #print(d)
        
        if not previous_product_data:
          report = "Unable to load previous product data.\n"
        elif d == {}:
          pass
        else:
            report = get_diff_report(d, previous_product_data, current_product_data, page, session )
            aggregate_report += url + "\n\n" + report
        
        # Cache the latest data in the same 
        try:
          with open(data_file, 'w') as f:
            json.dump(current_product_data, f, ensure_ascii=False)
        except OSError as ose:
          aggregate_report += "Error caching latest data.\n"
          print("Error saving file")
    
    except Exception as e:
      #print(d)
      aggregate_report += url + "\n\nError: " + str(e) + "\n"
      traceback.print_exc()

  if aggregate_report.strip():
    print( aggregate_report )
    #send_notification( "Patchwerks Update", aggregate_report)
  else:
    print( "No changes detected")
      

