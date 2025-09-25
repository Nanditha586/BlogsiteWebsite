from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create_post, name='create_post'),
    path('login/', views.login, name='login'),  # fixed to point to correct login view
    path('register/', views.registerview, name='register'),  # use only registerview
    path('posts/',views.posts,name='posts'),
    path('profilepage/', views.profilepage, name='profilepage'),
    path('logout/',views.logout,name='logout'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('myposts/', views.myposts, name='myposts'),
    path('edit_myposts/<str:title>/', views.edit_myposts, name='edit_myposts'),
    path('delete_myposts/', views.delete_myposts, name='delete_myposts'),
    path('aboutauthor/<str:username>/', views.aboutauthor, name='aboutauthor'),
    path('followers/<str:username>/', views.followers, name='followers'),
    path('following/<str:username>/', views.following, name='following'),
    path('profilefollower/<str:username>/', views.profilefollower, name='profilefollower'),
    path('profilefollowing/<str:username>/', views.profilefollowing, name='profilefollowing'),
    path('toggle-follow/', views.toggle_follow, name='toggle_follow'),
    path('toggle_like/', views.toggle_like, name='toggle_like'),
    path('add_comment/', views.add_comment, name='add_comment'),
    




]
