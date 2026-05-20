import numpy as np
from PIL import Image as PILImage, ImageFilter, ImageChops

# Create a mock raster with NaNs
raster = np.full((10, 10), np.nan, dtype=np.float32)
raster[2:8, 2:8] = 0.5  # Inner valid square

# Similar to the original code
nan_mask = np.isnan(raster)
h, w = raster.shape
rgba = np.zeros((h, w, 4), dtype=np.uint8)
for i in range(h):
    for j in range(w):
        if nan_mask[i, j]:
            rgba[i, j] = (0, 0, 0, 0)
        else:
            rgba[i, j] = (0, 255, 0, 255) # Green inside

img = PILImage.fromarray(rgba, "RGBA")
output_size = (100, 100)
smooth = True

if output_size:
    img = img.resize(output_size, PILImage.NEAREST)
    crisp_alpha = img.split()[3]

    if smooth:
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

    eroded_alpha = crisp_alpha.filter(ImageFilter.MinFilter(3))
    boundary_mask = ImageChops.subtract(crisp_alpha, eroded_alpha)
    
    stroke = PILImage.new("RGBA", img.size, (255, 255, 255, 255))
    img.paste(stroke, (0, 0), boundary_mask)

img.save("data/test_boundary.png")
print("Saved data/test_boundary.png")
