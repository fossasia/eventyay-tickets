#!/bin/bash

set -e



for img in ../src/screens/website/cfp_start.png ../src/screens/website/cfp_settings.png  ../src/screens/website/agenda_public.png ; do
    base_name=$(basename "$img" .png)  # Extract the base name for saving output
    echo "Processing $img... to $base_name.png"
    magick $img \
        -resize 1024x \
        -gravity north -crop 1024x576+0+0 +repage \
        "${base_name}.png"

    # Create the rounded corner mask and the rounded corner overlay
    magick $base_name.png \
          -format 'roundrectangle 1,1 %[fx:w+4],%[fx:h+4] 15,15'\
          info: > rounded_corner.mvg
    magick $base_name.png \
         -border 3 -alpha transparent \
         -background none -fill white -stroke none -strokewidth 0 \
         -draw "@rounded_corner.mvg"    rounded_corner_mask.png
    magick $base_name.png -border 3 -alpha transparent \
          -background none -fill none -stroke black -strokewidth 12 \
          -draw "@rounded_corner.mvg"    rounded_corner_overlay.png
    magick $base_name.png -alpha set -bordercolor none -border 3  \
          rounded_corner_mask.png -compose DstIn -composite \
          rounded_corner_overlay.png -compose Over -composite \
          bordered_$base_name.png
    rm rounded_corner.mvg rounded_corner_mask.png rounded_corner_overlay.png $base_name.png
done

echo "Combining images..."
magick bordered_cfp_start.png bordered_cfp_settings.png bordered_agenda_public.png +smush 4 screenshots.png  # Combine images horizontally

rm bordered*.png  # Clean up intermediate files
