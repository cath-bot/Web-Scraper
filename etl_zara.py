from datetime import datetime
import pandas as pd

# from postgres_connection import connect_to_db, disconnect_from_db
from s3_bucket import *
from get_zara import extract_products
from logger import setup_logger

logger = setup_logger()
# date = datetime.now().strftime('%Y-%m-%d')
date = '2023-07-23'

def normalize_related_products():
    '''docstring here'''
    related_products_dict = get_bucket_file(f'{date}-related_products.json')
    data = []
    for product, products in related_products_dict.items():
        for related_product in products:
            data.append({
                "product_id": product,
                "related_product_id": related_product
            })
    related_products = pd.DataFrame(data)
    return related_products
            
def extract_subcategories(subcategories):
    '''docstring here'''
    ignore_ids = [
        '194501' , '2118764', 
        '2292949', '2292271', 
        '1950810', '1890848',
        '2307636', '2307635',
        '2307136',
        ]
    ignore_names = [
        'DISCOVER', 'JOIN LIFE', 'CAREERS'
    ]
    categories = []
    for subcategory in subcategories:
        subcategory_name = subcategory['name']
        subcategory_id = str(subcategory['id'])
        age_range = None
        if subcategory_id in ignore_ids:
            continue
        elif 'DIVIDER' in subcategory_name or subcategory_name in ignore_names:
            continue
        elif '|' in subcategory_name:
            if ('BABY' in subcategory_name or 'GIRL' in subcategory_name 
            or 'BOY' in subcategory_name):
                transform_cat = subcategory_name.split('|')
                subcategory_name = transform_cat[1]
                age_range = transform_cat[0]
            else:
                subcategory_name = subcategory_name.replace('|', 'AND')
        categories.append({
            'subcategory_id': subcategory_id,
            'category': subcategory_name,
            'age_range': age_range
            })
    return categories

def normalize_categories():
    '''docstring here'''
    categories_dict = get_bucket_file(f'{date}-categories.json')
    categories_dict = categories_dict['categories']

    # normalizing target_groups
    categories = []
    target_groups = []
    categories_by_target_group = []
    for entry in categories_dict:
        target_group = entry['name']
        target_group_id = entry['id']
        if (target_group == 'WOMAN' or 
            target_group == 'MAN' or target_group == 'KIDS'):
            target_groups.append({
                'target_group_id': str(target_group_id),
                'target_group': target_group
                })
        # normalizing subcategories
        categories_0 = extract_subcategories(entry['subcategories'])
        categories.extend(categories_0)
        # normalize categories by target_grooups
        temp = [
                {
                'target_group': entry['id'],
                'subcategory_id': value['subcategory_id']
                } for value in categories_0
            ]
        categories_by_target_group.append(temp)

        
    
    categories_by_target_group = flatten_and_convert_to_df(categories_by_target_group)
    target_groups = pd.DataFrame(target_groups)
    categories = pd.DataFrame(categories)

    return target_groups, categories, categories_by_target_group

# def products_to_df(list_of_products):
#     '''docstring here'''
#     df_products = pd.DataFrame(list_of_products)
#     return df_products

def extract_product_details(product_details, product_id):
    '''This function extracts care, certified materials, materials, and 
    origin details for a given product from the product details dataset.'''
    care, certified_materials, materials, origin = None, None, None, None
    for detail in product_details[product_id]:
        section_type = detail['sectionType']
        if section_type == 'care':
            care = detail
        elif section_type == 'certifiedMaterials':
            certified_materials = detail
        elif section_type == 'materials':
            materials = detail
        elif section_type == 'origin':
            origin = detail

    return [product_id, care, certified_materials, materials, origin]

def normalize_materials(materials, product_id):
    '''docstring here'''
    material_list = []
    attribute_name = None
    ignore = ['COMPOSITION', 'Which contains at least:']

    for item in materials['components']:
        if 'text' in item and 'value' in item['text']:
            if ('typography' in item['text'] and 
                item['text']['typography'] in ['heading-s', 'heading-xs']):
                attribute_name = item['text']['value']
                if attribute_name in ignore:
                    attribute_name = None
                    continue
            elif attribute_name is not None:
                attribute_value = item['text']['value']
                if attribute_value not in ignore:
                    if '<br>' in attribute_value:
                        attribute_value = attribute_value.split('<br>')
                        for item in attribute_value:
                            m = item.split('%')
                            percentage = f'{m[0]}%'
                            material = m[1]
                            material_list.append({
                                'product_id': product_id,
                                'material_part': attribute_name,
                                'percentage': percentage,
                                'material': material
                                })
                    else:
                        attribute_value = attribute_value.split('%')
                        percentage = f'{attribute_value[0]}%'
                        material = attribute_value[1]
                        material_list.append({
                            'product_id': product_id,
                            'material_part': attribute_name,
                            'percentage': percentage,
                            'material': material
                            })
    return material_list

def normalize_origin(origin, product_id):
    '''docstring here'''
    origin_list = []
    country_of_origin = origin['components'][-1]['text']['value']
    country_of_origin= country_of_origin.split('Made in')[1]
    origin_list.append({
                        'product_id': product_id,
                        'country_of_origin': country_of_origin
                        })
    return origin_list
    
def flatten_and_convert_to_df(obj):
    '''docstring here'''
    obj = [item for sublist in obj for item in sublist]
    df_obj = pd.DataFrame(obj)
    return df_obj

def organise_product_details():
    '''docstring here'''
    product_details = get_bucket_file(f'{date}-product_details.json')
    materials = []
    origin = []

    for product_id in product_details:
        extracted_details = extract_product_details(
            product_details,
            product_id
            )
        try:
            normalized_materials = normalize_materials(
                extracted_details[3],
                product_id
                )
            materials.append(normalized_materials)
        except Exception as e:
            logger.error(e)

        try:
            normalized_origin = normalize_origin(
                extracted_details[4],
                product_id
                )
            origin.append(normalized_origin)
        except Exception as e:
            logger.error(e)

    materials = flatten_and_convert_to_df(materials)
    origin = flatten_and_convert_to_df(origin)

    return materials, origin

# materials, origin = organise_product_details()
# related_products = normalize_related_products()
target_groups, categories, categories_by_target_group = normalize_categories()
print(categories)
print(target_groups)
print(categories_by_target_group)



