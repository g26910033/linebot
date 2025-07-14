from PIL import Image, ImageDraw

def create_rich_menu_image():
    """
    Creates a 2500x1686 image with a light grey background and lines for a 3x2 grid.
    """
    width, height = 2500, 1686
    bg_color = (240, 240, 240)  # Light grey
    line_color = (200, 200, 200) # Grey for lines
    
    image = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    # Draw vertical lines
    draw.line([(width / 3, 0), (width / 3, height)], fill=line_color, width=5)
    draw.line([(width * 2 / 3, 0), (width * 2 / 3, height)], fill=line_color, width=5)

    # Draw horizontal line
    draw.line([(0, height / 2), (width, height / 2)], fill=line_color, width=5)

    image.save('scripts/rich_menu_background.png')
    print("Image 'scripts/rich_menu_background.png' created successfully.")

if __name__ == "__main__":
    create_rich_menu_image()
