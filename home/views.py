from django.shortcuts import render, HttpResponse, redirect
# from .models import Signup
from django.http import JsonResponse

import random
import string
# from .models import Event

# Create your views here.
def index(request):
    return render(request, "home/index.html")




# # def login(request):
# #     if request.method == "POST":
# #         form_type = request.POST.get('form_type')

# #         if form_type == "signup":
# #             name = request.POST.get('signup-name')
# #             email = request.POST.get('signup-email')
# #             password = request.POST.get('signup-password')

# #             # Save the user
# #             new_user = Signup(name=name, email=email, password=password)
# #             new_user.save()

# #             return redirect('login')  # Redirect to login page after signup

# #         elif form_type == "login":
# #             email = request.POST.get('login-email')
# #             password = request.POST.get('login-password')

# #             try:
# #                 user = Signup.objects.get(email=email, password=password)

# #                 # Save user info to session
# #                 request.session['user_email'] = user.email
# #                 request.session['user_name'] = user.name

# #                 return redirect('dashboard')  # Redirect to dashboard
# #             except Signup.DoesNotExist:
# #                 return render(request, "login.html", {"error": "Invalid credentials"})

# #     return render(request, "login.html")

# # def host(request):
# #     name = request.session.get('user_name')
# #     if not name:
# #         return redirect('login')
# #     return render(request,"host.html")

# def album(request):
#     return render(request,"album.html")

# def guest_dashboard(request):
#     return render(request,"guest_dashboard.html")

# def host_dashboard(request):
#     return render(request,"host_dashboard.html")

# def centralised_album(request):
#     return render(request,"centralised_album.html")

# def dashboard(request):
#     name = request.session.get('user_name', None)
#     if not name:
#         return redirect('login')
#     return render(request, 'dashboard.html', {'name': name})
    
# def logout_view(request):
#     request.session.flush()  # Clears all session data
#     return redirect('login')  # Redirect to login page



# def generate_unique_event_code():
#     """Generates a unique 6-character event code."""
#     characters = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
#     while True:
#         code = ''.join(random.choices(characters, k=6))
#         if not Event.objects.filter(event_code=code).exists():
#             return code

# def host(request):
#     # Login check
#     if not request.session.get('user_email'):
#         if request.method == "POST":
#             return JsonResponse({'success': False, 'error': 'User not logged in'}, status=403)
#         return redirect('login')

#     if request.method == "POST":
#         try:
#             created_by = Signup.objects.get(email=request.session.get('user_email'))
#         except Signup.DoesNotExist:
#             return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

#         event_name = request.POST.get('event_name')
#         event_date = request.POST.get('event_date')
#         event_time = request.POST.get('event_time')
#         location = request.POST.get('location')
#         description = request.POST.get('description')
#         privacy = request.POST.get('privacy')
#         allow_upload = bool(request.POST.get('allow_upload'))
#         allow_download = bool(request.POST.get('allow_download'))
#         allow_tag = bool(request.POST.get('allow_tag'))
#         allow_comment = bool(request.POST.get('allow_comment'))
#         theme_color = request.POST.get('theme_color')
#         cover_photo = request.FILES.get('cover_photo')

#         event_code = generate_unique_event_code()

#         event = Event(
#             event_name=event_name,
#             event_date=event_date,
#             event_time=event_time,
#             location=location,
#             description=description,
#             privacy=privacy,
#             allow_upload=allow_upload,
#             allow_download=allow_download,
#             allow_tag=allow_tag,
#             allow_comment=allow_comment,
#             theme_color=theme_color,
#             cover_photo=cover_photo,
#             event_code=event_code,
#             created_by=created_by
#         )
#         event.save()

#         return JsonResponse({'success': True, 'event_code': event_code})

#     # GET request
#     return render(request, "host.html")
