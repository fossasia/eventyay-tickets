from django.forms import RadioSelect


class HeaderSelect(RadioSelect):
    option_template_name = 'orga/widgets/header_option.html'
