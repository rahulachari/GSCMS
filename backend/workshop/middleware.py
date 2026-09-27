from django.contrib.auth.models import User

class AutoLoginMiddleware:
    """
    Automatically authenticates all requests as the Workshop Owner
    so users and Karigars can access the system immediately without logging in.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            owner = User.objects.filter(username='owner').first()
            if not owner:
                owner = User.objects.filter(is_superuser=True).first()
            if not owner:
                owner = User.objects.create_superuser('owner', 'owner@swarna.com', 'admin123')
            request.user = owner
        return self.get_response(request)
