python3 parser.py \
  --dxf ../dxfs/good.dxf \
  --img ../plan_imgs/MEL_5152_EG_ELT051_A_Z_page-0001.jpg \
  --out annotated.png \
  --json out.json \
  --calib '282.14,1169.69:885,588;282.14,513:885,4460;522.14,820.16:2300,2650' \
  --radius 24 \
  --assoc_max_dist 300 \
  --label_assoc_max_dist 60 \
  --label_layer_regex 'TXT|Beschrift|Label|Text' \
  --label_name_regex  'Bauteilbeschrift|Beschrift|Label|Text' \
  --device_prefixes 'Steckdosenverteiler_' \
  --category_filter 'electrical'

