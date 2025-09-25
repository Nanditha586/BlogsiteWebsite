from django.shortcuts import render, get_object_or_404
from .models import BlogPost
from .forms import BlogPostForm
from django.shortcuts import render, redirect
from django.contrib import messages
import mysql.connector
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db import models

def home(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'blog/home.html', {'posts': posts})

def post_detail(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    return render(request, 'blog/post_detail.html', {'post': post})

def create_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to homepage after saving
    else:
        form = BlogPostForm()
    return render(request, 'blog/create_post.html', {'form': form})
def register(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to homepage after saving
    else:
        form = BlogPostForm()
    return render(request, 'blog/register.html', {'form': form})

def loginpage(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to homepage after saving
    else:
        form = BlogPostForm()
    return render(request, 'blog/loginpage.html', {'form': form})

def registerview(request):
    if request.method == "POST":
        username = request.POST['username']
        phonenumber = request.POST['phonenumber']
        email = request.POST['email']
        password = request.POST['password']

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogpost"
        )
        mycursor = conn.cursor()

        # Check if email already exists
        mycursor.execute("SELECT * FROM register WHERE email = %s", (email,))
        result = mycursor.fetchone()

        if result:
            return render(request, "register.html", {"status": "Email already registered"})
        else:
            mycursor.execute(
                "INSERT INTO register (username, phonenumber, email, password) VALUES (%s, %s, %s, %s)",
                (username, phonenumber, email, password)
            )
            conn.commit()
            return redirect('loginpage')  # You must have 'login' in your urls.py name attribute
    else:
        return render(request, 'register.html')

def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogpost"
        )
        mycursor = conn.cursor()
        mycursor.execute("SELECT * FROM register WHERE email = %s AND password = %s", (email, password))
        result = mycursor.fetchone()

        if result:
            request.session['email'] = email  # or store username if needed
            return render(request, "form.html")
        else:
            return render(request, "loginpage.html", {"status": "Invalid credentials"})
    else:
        return render(request, 'loginpage.html')



def create_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = BlogPostForm()
    return render(request, 'blog/create_post.html', {'form': form})



def aboutauthor(request, username):
    if not username:
        return redirect('posts')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    logged_in_user = request.session.get('username')

    # Handle Follow / Like / Comment actions
    if request.method == "POST" and request.session.get('email'):
        if 'follow_author' in request.POST:
            author_to_follow = request.POST.get('follow_author')
            cursor.execute("""
                SELECT * FROM followers 
                WHERE follower_username=%s AND following_author=%s
            """, (logged_in_user, author_to_follow))
            already_following = cursor.fetchone()

            if not already_following:
                today = date.today()
                cursor.execute("""
                    INSERT INTO followers (follower_username, following_author, date_followed)
                    VALUES (%s, %s, %s)
                """, (logged_in_user, author_to_follow, today))
            else:
                cursor.execute("""
                    DELETE FROM followers 
                    WHERE follower_username=%s AND following_author=%s
                """, (logged_in_user, author_to_follow))
            conn.commit()

        elif 'like_post' in request.POST:
            post_title = request.POST.get('like_post')
            cursor.execute("SELECT * FROM likes WHERE post_title=%s AND username=%s", (post_title, logged_in_user))
            already_liked = cursor.fetchone()
            if not already_liked:
                cursor.execute("INSERT INTO likes (post_title, username) VALUES (%s, %s)", (post_title, logged_in_user))
                cursor.execute("UPDATE postcreation SET likes = likes + 1 WHERE title = %s", (post_title,))
            else:
                cursor.execute("DELETE FROM likes WHERE post_title=%s AND username=%s", (post_title, logged_in_user))
                cursor.execute("UPDATE postcreation SET likes = likes - 1 WHERE title = %s AND likes > 0", (post_title,))
            conn.commit()

        elif 'comment' in request.POST:
            comment_text = request.POST.get('comment')
            post_title = request.POST.get('post_title')
            if comment_text.strip():
                today = date.today()
                now = datetime.now().strftime("%H:%M:%S")
                cursor.execute("""
                    INSERT INTO comments (post_title, commenter, comment, date, time)
                    VALUES (%s, %s, %s, %s, %s)
                """, (post_title, logged_in_user, comment_text, today, now))
                conn.commit()

    # Fetch author details
    cursor.execute("""
        SELECT username, email, phonenumber, profilephoto, bio
        FROM register 
        WHERE username = %s
    """, (username,))
    author = cursor.fetchone()

    if author and author['profilephoto']:
        author['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(author['profilephoto']).decode('utf-8')
    else:
        author['profilephoto'] = "/static/images/default.png"

    # Author stats
    cursor.execute("SELECT COUNT(*) AS total_posts FROM postcreation WHERE author=%s", (username,))
    author['total_posts'] = cursor.fetchone()['total_posts']

    cursor.execute("SELECT COUNT(*) AS total_followers FROM followers WHERE following_author=%s", (username,))
    author['total_followers'] = cursor.fetchone()['total_followers']

    cursor.execute("SELECT COUNT(*) AS total_following FROM followers WHERE follower_username=%s", (username,))
    author['total_following'] = cursor.fetchone()['total_following']

    # Check if logged user follows the author
    is_following = False
    if logged_in_user:
        cursor.execute("""
            SELECT 1 FROM followers 
            WHERE follower_username=%s AND following_author=%s
        """, (logged_in_user, username))
        is_following = cursor.fetchone() is not None

    # Fetch author's posts
    cursor.execute("""
        SELECT title, content, blogphoto, date, time, likes
        FROM postcreation
        WHERE author = %s
        ORDER BY date DESC, time DESC
    """, (username,))
    posts = cursor.fetchall()

    for post in posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')

        # Check if logged user liked the post
        if logged_in_user:
            cursor.execute("SELECT 1 FROM likes WHERE post_title=%s AND username=%s", (post['title'], logged_in_user))
            post['is_liked'] = cursor.fetchone() is not None
        else:
            post['is_liked'] = False

        # Fetch comments for this post
        cursor.execute("""
            SELECT commenter, comment, date, time
            FROM comments
            WHERE post_title=%s
            ORDER BY date DESC, time DESC
        """, (post['title'],))
        post['comments'] = cursor.fetchall()

    conn.close()

    return render(request, 'blog/aboutauthor.html', {
        'author': author,
        'posts': posts,
        'is_following': is_following,
        'logged_in_user': logged_in_user
    })
