def write_qrcode_image(data, out):
    """Write a QR code image for data to out.

    The written image is in image/svg+xml format.

    One of `qrcode` or `segno` are required. If neither is found, raises
    ModuleNotFoundError.
    """
    try:
        import qrcode
        import qrcode.image.svg

        img = qrcode.make(data, image_factory=qrcode.image.svg.SvgImage)
        img.save(out)
    except ModuleNotFoundError:
        import segno

        img = segno.make(data)
        img.save(out, kind='svg')
