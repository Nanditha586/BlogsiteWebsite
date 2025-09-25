from datetime import date, datetime
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from .models import BlogPost, Post
from .forms import BlogPostForm
from django.http import HttpResponse
import mysql.connector
from django.contrib import messages
from django.core.paginator import Paginator 
from collections import defaultdict
import base64
import os

# Home page view: Shows all blog posts in descending order of creation time
def home(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'blog/home.html', {'posts': posts})


# Post detail page: Fetches a single blog post by its ID
def post_detail(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    return render(request, 'blog/post_detail.html', {'post': post})


# User Registration view
def registerview(request):
    if request.method == "POST":
        # Get form values from request
        username = request.POST.get('username')
        phonenumber = request.POST.get('phonenumber')
        email = request.POST.get('email')
        password = request.POST.get('password')
        profilephoto=request.FILES.get('profilephoto')
        bio=request.POST.get('bio')

        # Connect to MySQL
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogposts"
        )
        mycursor = conn.cursor()

        # Check if email or username already exists
        mycursor.execute("SELECT * FROM register WHERE email = %s", (email,))
        email_exists = mycursor.fetchone()
        mycursor.execute("SELECT * FROM register WHERE username = %s", (username,))
        username_exists = mycursor.fetchone()

        if email_exists:
            messages.error(request, "⚠️ Email already exists! Please use another email.")
            conn.close()
            return redirect('register')
        elif username_exists:
            messages.error(request, "⚠️ Username already exists! Please choose another username.")
            conn.close()
            return redirect('register')
        else:
            # Convert profile photo to binary for storage
            photo_data = None
            if profilephoto:
                photo_data = profilephoto.read()

            # Insert new user into database
            mycursor.execute(
                "INSERT INTO register (username, phonenumber, email, password, profilephoto) VALUES (%s, %s, %s, %s, %s)",
                (username, phonenumber, email, password, photo_data)
            )
            conn.commit()
            conn.close()
            messages.success(request, "Registered successfully! You can login now.")
            return redirect('register')
    else:
        return render(request, 'blog/register.html')


# User Login view
def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        # Connect to DB
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogposts"
        )
        mycursor = conn.cursor(dictionary=True)
        # Check if email and password match
        mycursor.execute("SELECT * FROM register WHERE email = %s AND password = %s", (email, password))
        result = mycursor.fetchone()
        conn.close()

        if result:
            # Save user info in session
            request.session['email'] = result['email']
            request.session['username']=result['username']
            return redirect('posts')  # Redirect to posts page
        else:
            messages.error(request, "❌ Invalid credentials")
            return render(request, "blog/login.html")
    else:
        return render(request, 'blog/login.html')


# Create a new blog post
def create_post(request):
    # User must be logged in
    if not request.session.get('email'):
        messages.error(request, "⚠️ Please login to create a post.")
        return redirect('login')

    username = request.session.get('username')

    if request.method == "POST":
        # Get form inputs
        title = request.POST.get('title')
        category=request.POST.get('category')
        content = request.POST.get('content')
        date=request.POST.get('date')
        time=request.POST.get('time')
        blogphoto = request.FILES.get('blogphoto')
        
        # Connect to DB
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogposts"
        )
        mycursor = conn.cursor(dictionary=True)
        
        # Check if title already exists
        mycursor.execute("SELECT * FROM postcreation WHERE title = %s", (title,))
        result = mycursor.fetchone()
        
        if result:
            conn.close()
            messages.error(request, "⚠️ Title already exists! Please choose another title.")
            return redirect('create_post')
        else:
            # Convert photo to binary
            image_name = None
            if blogphoto:
                image_name = blogphoto.read()

            # Insert post into DB
            mycursor.execute(
                "INSERT INTO postcreation (title, category, content, blogphoto, author, date, time) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (title, category, content,image_name, username, date, time )
            )
            conn.commit()
            conn.close()
            messages.success(request, "✅ Post added successfully!")
            return redirect('create_post')
    return render(request, 'blog/create_post.html', {'username': username})


# Show all posts with pagination, search, filter, likes, and comments
def posts(request):
    page_number = request.GET.get('page', 1)
    selected_categories = request.GET.getlist('categories')
    search_query = request.GET.get('q', '')

    # Connect to DB
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    mycursor = conn.cursor(dictionary=True)
    post_modal_to_open = None

    # Handle POST actions (comments or likes)
    if request.method == "POST" and request.session.get('email'):
        username = request.session.get('username')

        # Add comment
        if 'comment' in request.POST:
            comment_text = request.POST.get('comment')
            post_title = request.POST.get('post_title')
            today = date.today()
            now = datetime.now().strftime("%H:%M:%S")

            if comment_text.strip():
                mycursor.execute("""
                    INSERT INTO comments (post_title, commenter, comment, date, time)
                    VALUES (%s, %s, %s, %s, %s)
                """, (post_title, username, comment_text, today, now))
                conn.commit()
            
        # Handle Like/Unlike
        elif 'like_post' in request.POST:
            post_title = request.POST.get('like_post')

            # Check if already liked
            mycursor.execute("SELECT * FROM likes WHERE post_title=%s AND username=%s", (post_title, username))
            already_liked = mycursor.fetchone()

            if not already_liked:
                # Add like
                mycursor.execute("INSERT INTO likes (post_title, username) VALUES (%s, %s)", (post_title, username))
                mycursor.execute("UPDATE postcreation SET likes = likes + 1 WHERE title = %s", (post_title,))
                conn.commit()
            else:
                # Remove like (toggle dislike)
                mycursor.execute("DELETE FROM likes WHERE post_title=%s AND username=%s", (post_title, username))
                mycursor.execute("UPDATE postcreation SET likes = likes - 1 WHERE title = %s AND likes > 0", (post_title,))
                conn.commit()
            
            
            # Handle Follow/Unfollow
        elif 'follow_author' in request.POST:
            author_to_follow = request.POST.get('follow_author')
            username = request.session.get('username')

    # Check if already following
            mycursor.execute("""
            SELECT * FROM followers 
            WHERE follower_username=%s AND following_author=%s
            """, (username, author_to_follow))
            already_following = mycursor.fetchone()

            if not already_following:
        # Follow the author
                today = date.today()
                mycursor.execute("""
                    INSERT INTO followers (follower_username, following_author, date_followed)
                    VALUES (%s, %s, %s)
                    """, (username, author_to_follow, today))
                conn.commit()
            else:
        # Unfollow the author
                mycursor.execute("""
                    DELETE FROM followers 
                    WHERE follower_username=%s AND following_author=%s
                    """, (username, author_to_follow))
                conn.commit()

        

    # Fetch all posts with optional search and filters
    query = """
    SELECT p.title, p.content, p.blogphoto, p.author, p.date, p.time, p.likes, r.profilephoto, p.category
    FROM postcreation p
    JOIN register r ON p.author = r.username
    WHERE 1=1
    """
    params = []

    # Search filter
    if search_query:
        query += " AND (p.title LIKE %s OR p.author LIKE %s OR p.date LIKE %s OR p.category LIKE %s)"
        params.extend(['%' + search_query + '%'] * 4)

    # Category filter
    if selected_categories:
        query += " AND p.category IN ({})".format(",".join(["%s"] * len(selected_categories)))
        params.extend(selected_categories)

    query += " ORDER BY p.date DESC, p.time DESC"
    mycursor.execute(query, params)
    all_posts = mycursor.fetchall()

    # Convert images and fetch comments for each post
    for post in all_posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
        if post['profilephoto']:
            post['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(post['profilephoto']).decode('utf-8')
        else:
            post['profilephoto'] = "/static/images/default.png"

        # Fetch comments for each post
        mycursor.execute("""
            SELECT commenter, comment, date, time
            FROM comments
            WHERE post_title = %s
            ORDER BY date DESC, time DESC
        """, (post['title'],))
        post['comments'] = mycursor.fetchall()

        # Check if current user liked this post
        if request.session.get('email'):
            username = request.session.get('username')
            mycursor.execute("SELECT 1 FROM likes WHERE post_title=%s AND username=%s", (post['title'], username))
            post['is_liked'] = mycursor.fetchone() is not None
        else:
            post['is_liked'] = False

        mycursor.execute("""
            SELECT 1 FROM followers 
            WHERE follower_username=%s AND following_author=%s
        """, (username, post['author']))
        post['is_following'] = mycursor.fetchone() is not None

    conn.close()

    # Paginate posts (6 per page)
    paginator = Paginator(all_posts, 6 )
    page_obj = paginator.get_page(page_number)

    return render(request, 'blog/posts.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_categories': selected_categories,
        'post_modal_to_open': post_modal_to_open,
    })

def profilepage(request):
    if not request.session.get('email'):
        return redirect('login')

    email = request.session['email']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    # Get user details
    cursor.execute("SELECT username, phonenumber, email, password, profilephoto, bio FROM register WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        if user['username']:
            user['username'] = user['username'].capitalize()
        if user['profilephoto']:
            user['profilephoto'] = base64.b64encode(user['profilephoto']).decode('utf-8')

        # Count Followers → users who follow me
        cursor.execute("SELECT COUNT(*) AS followers FROM followers WHERE following_author = %s", (user['username'],))
        user['followers'] = cursor.fetchone()['followers']

        # Count Following → users I follow
        cursor.execute("SELECT COUNT(*) AS following FROM followers WHERE follower_username = %s", (user['username'],))
        user['following'] = cursor.fetchone()['following']

    conn.close()
    return render(request, 'blog/profilepage.html', {'user': user})


# User Logout
def logout(request):
    try:
        # Remove email from session if exists
        if('email' in request.session):
             del request.session["email"]
    except KeyError:
        pass
    return redirect('login')


def edit_profile(request):
    if not request.session.get('email'):
        return redirect('login')

    email = request.session['email']

    if request.method == "POST":
        username = request.POST.get('username')
        phonenumber = request.POST.get('phonenumber')
        password = request.POST.get('password')
        profilephoto = request.FILES.get('profilephoto')
        remove_photo = request.POST.get('remove_photo')
        bio=request.POST.get('bio')

        conn = mysql.connector.connect(
            host="localhost", user="root", password="", database="blogposts"
        )
        cursor = conn.cursor()

        # Get old password if new one not provided
        if not password or not password.strip():
            cursor.execute("SELECT password FROM register WHERE email=%s", (email,))
            row = cursor.fetchone()
            if row:
                password = row[0]
        
        if profilephoto:
            photo_data = profilephoto.read()
            cursor.execute("""
                UPDATE register 
                SET username=%s, phonenumber=%s, password=%s, profilephoto=%s, bio=%s
                WHERE email=%s
            """, (username, phonenumber, password, photo_data, bio, email))
        
        elif remove_photo:
            cursor.execute("""
                UPDATE register 
                SET username=%s, phonenumber=%s, password=%s, profilephoto=NULL, bio=%s
                WHERE email=%s
            """, (username, phonenumber, password,bio, email))
        else:
            cursor.execute("""
                UPDATE register 
                SET username=%s, phonenumber=%s, password=%s,  bio=%s
                WHERE email=%s
            """, (username, phonenumber, password, email))

        conn.commit()
        print("Rows affected:", cursor.rowcount)  # Debugging
        conn.close()

        if cursor.rowcount > 0:
            request.session['username'] = username
            messages.success(request, "Profile updated successfully!")
        else:
            messages.error(request, "Profile not updated. Please check your data.")

        return redirect('profilepage')


# Show all posts created by the logged‑in user
def myposts(request):
    if not request.session.get('email'):
        return redirect('login')

    username = request.session.get('username')  # current author
    page_number = request.GET.get('page', 1)

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
        
    cursor = conn.cursor(dictionary=True)
    # Get all posts created by the logged-in user
    cursor.execute("SELECT title,category, content, blogphoto, author,date,time FROM postcreation WHERE author = %s ORDER BY date DESC, time DESC", (username,))
    
    user_posts = cursor.fetchall()

    # Convert each post's blog photo to base64 & fetch comments
    for post in user_posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
        cursor.execute("""
            SELECT commenter, comment, date, time
            FROM comments
            WHERE post_title = %s
            ORDER BY date DESC, time DESC
        """, (post['title'],))
        post['comments'] = cursor.fetchall()
    
    conn.close()

    # Paginate user posts (3 per page)
    paginator = Paginator(user_posts, 3)  
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'blog/myposts.html', {'user_posts': user_posts, 'username': username, 'page_obj': page_obj})
    

# Edit a specific post created by the logged‑in user
def edit_myposts(request, title):
    if not request.session.get('email'):
        messages.error(request, "⚠️ Please login to edit posts.")
        return redirect('login')

    username = request.session.get('username')

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        # Collect updated post details
        new_title = request.POST.get('title')
        category = request.POST.get('category')
        content = request.POST.get('content')
        original_title = request.POST.get('original_title')  # hidden input to store original title
        date = request.POST.get('date')
        time = request.POST.get('time')
        blogphoto = request.FILES.get('blogphoto')
        remove_photo = request.POST.get('remove_photo')

        if blogphoto:
            # Update with a new uploaded photo
            image_data = blogphoto.read()
            cursor.execute("""
                UPDATE postcreation 
                SET title=%s, category=%s, content=%s, blogphoto=%s, date=%s, time=%s 
                WHERE title=%s AND author=%s
            """, (new_title, category, content, image_data, date, time, original_title, username))
        
        elif remove_photo:
            # User chose to remove photo
            cursor.execute("""
                UPDATE postcreation 
                SET title=%s, category=%s, content=%s, blogphoto=NULL, date=%s, time=%s 
                WHERE title=%s AND author=%s
                """, (new_title, category, content, date, time, original_title, username))
        else:
            # Keep the old image
            cursor.execute("""
            UPDATE postcreation 
            SET title=%s, category=%s, content=%s, date=%s, time=%s 
            WHERE title=%s AND author=%s
            """, (new_title, category, content, date, time, original_title, username))

        conn.commit()
        conn.close()

        messages.success(request, "✅ Post updated successfully!")
        return redirect('myposts')

    else:
        # Fetch the post for editing
        cursor.execute("SELECT * FROM postcreation WHERE title=%s AND author=%s", (title, username))
        post = cursor.fetchone()
        conn.close()

        if not post:
            messages.error(request, "⚠️ Post not found or you don't have permission to edit it.")
            return redirect('myposts')

        # Convert image if exists
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
        else:
            post['blogphoto'] = None

        return render(request, 'blog/edit_post.html', {'post': post})


# Delete a post created by the logged‑in user
def delete_myposts(request):
    if not request.session.get('email'):
        messages.error(request, "⚠️ Please login to delete posts.")
        return redirect('login')

    if request.method == "POST":
        title = request.POST.get("title")
        author = request.POST.get("author")

        print("DEBUG: Trying to delete ->", title, author)  # Debugging

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogposts"
        )
        cursor = conn.cursor()
        # Delete post matching the title and author
        cursor.execute("DELETE FROM postcreation WHERE title = %s AND author = %s", (title, author))
        conn.commit()
        print("DEBUG: Rows affected ->", cursor.rowcount)  # Debugging
        conn.close()

        if cursor.rowcount == 0:
            messages.error(request, f"⚠️ Could not find post '{title}' by {author} to delete.")
        else:
            messages.success(request, "🗑️ Post deleted successfully!")

        return redirect('myposts')

from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from datetime import date, datetime
import mysql.connector, base64

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
    if request.method == "POST" and request.session.get('email'):
        if 'post_title' in request.POST:
            post_title = request.POST.get('post_title')
            cursor.execute("SELECT * FROM likes WHERE post_title=%s AND username=%s", (post_title, logged_in_user))
            already_liked = cursor.fetchone()

            if not already_liked:
                cursor.execute("INSERT INTO likes (post_title, username) VALUES (%s, %s)", (post_title, logged_in_user))
                cursor.execute("UPDATE postcreation SET likes = likes + 1 WHERE title=%s", (post_title,))
            else:
                cursor.execute("DELETE FROM likes WHERE post_title=%s AND username=%s", (post_title, logged_in_user))
                cursor.execute("UPDATE postcreation SET likes = likes - 1 WHERE title=%s AND likes > 0", (post_title,))

            conn.commit()

            cursor.execute("SELECT likes FROM postcreation WHERE title=%s", (post_title,))
            likes_count = cursor.fetchone()['likes']

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'likes': likes_count,
                    'is_liked': not bool(already_liked)
                })
    conn.close()

    return render(request, 'blog/aboutauthor.html', {
        'author': author,
        'posts': posts,
        'is_following': is_following,
        'logged_in_user': logged_in_user
    })


def followers(request, username):
    if not request.session.get('username'):
        return redirect('login')  # ensure user is logged in

    logged_in_user = request.session['username']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    # Handle follow/unfollow form
    if request.method == "POST":
        follow_author = request.POST.get('follow_author')

        # Check if already following
        cursor.execute("SELECT * FROM followers WHERE follower_username=%s AND following_author=%s",
                       (logged_in_user, follow_author))
        existing = cursor.fetchone()

        if existing:
            # Unfollow
            cursor.execute("DELETE FROM followers WHERE follower_username=%s AND following_author=%s",
                           (logged_in_user, follow_author))
        else:
            # Follow
            cursor.execute("INSERT INTO followers (follower_username, following_author, date_followed) VALUES (%s, %s, %s)",
                           (logged_in_user, follow_author, date.today()))
        conn.commit()

        return redirect('followers', username=username)

    # Get followers list
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username = %s THEN TRUE 
            ELSE FALSE 
        END as is_following
        FROM followers f
        JOIN register r ON f.follower_username = r.username
        LEFT JOIN followers f2 ON f2.follower_username = %s AND f2.following_author = r.username
        WHERE f.following_author = %s
    """, (logged_in_user, logged_in_user, username))

    followers = cursor.fetchall()

    # Convert profilephoto from BLOB to Base64 string
    for follower in followers:
        if follower['profilephoto']:
            follower['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(follower['profilephoto']).decode('utf-8')
        else:
            follower['profilephoto'] = "/static/images/default.png"

    # Get author details
    cursor.execute("""
        SELECT username, email, phonenumber, profilephoto, bio
        FROM register 
        WHERE username = %s
    """, (username,))
    author = cursor.fetchone()

    conn.close()

    return render(request, 'blog/followers.html', {
        'followers': followers,
        'author_username': username,
        'author': author
    })


def following(request, username):
    if not request.session.get('username'):
        return redirect('login')

    logged_in_user = request.session['username']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    # Get list of people the user is following
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username = %s THEN TRUE 
            ELSE FALSE 
        END as is_following
        FROM followers f
        JOIN register r ON f.following_author = r.username
        LEFT JOIN followers f2 ON f2.follower_username = %s AND f2.following_author = r.username
        WHERE f.follower_username = %s
    """, (logged_in_user, logged_in_user, username))

    following = cursor.fetchall()

    # Convert BLOB photos to base64
    for person in following:
        if person['profilephoto']:
            person['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(person['profilephoto']).decode('utf-8')
        else:
            person['profilephoto'] = "/static/images/default.png"

    cursor.close()
    conn.close()

    return render(request, 'blog/following.html', {
        'following': following,
        'author_username': username
    })






def profilefollowing(request, username):
    if not request.session.get('username'):
        return redirect('login')

    logged_in_user = request.session['username']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    # Handle follow/unfollow toggle
    if request.method == "POST":
        follow_author = request.POST.get('follow_author')
        cursor.execute("SELECT * FROM followers WHERE follower_username=%s AND following_author=%s",
                       (logged_in_user, follow_author))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("DELETE FROM followers WHERE follower_username=%s AND following_author=%s",
                           (logged_in_user, follow_author))
        else:
            cursor.execute("INSERT INTO followers (follower_username, following_author, date_followed) VALUES (%s, %s, %s)",
                           (logged_in_user, follow_author, date.today()))
        conn.commit()
        return redirect('profilefollowing', username=username)  # stay in the same page

    # Get list of people the author is following
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username = %s THEN TRUE 
            ELSE FALSE 
        END as is_following
        FROM followers f
        JOIN register r ON f.following_author = r.username
        LEFT JOIN followers f2 
            ON f2.follower_username = %s 
           AND f2.following_author = r.username
        WHERE f.follower_username = %s
    """, (logged_in_user, logged_in_user, username))

    following = cursor.fetchall()

    # Convert BLOB to Base64
    for person in following:
        if person['profilephoto']:
            person['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(person['profilephoto']).decode('utf-8')
        else:
            person['profilephoto'] = "/static/images/default.png"

    conn.close()

    return render(request, 'blog/profilefollowing.html', {  # use correct template
        'following': following,
        'author_username': username
    })

def profilefollower(request, username):
    if not request.session.get('username'):
        return redirect('login')

    logged_in_user = request.session['username']

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="blogposts"
    )
    cursor = conn.cursor(dictionary=True)

    # Handle follow/unfollow POST
    if request.method == "POST":
        follow_author = request.POST.get('follow_author')
        cursor.execute("SELECT * FROM followers WHERE follower_username=%s AND following_author=%s",
                       (logged_in_user, follow_author))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("DELETE FROM followers WHERE follower_username=%s AND following_author=%s",
                           (logged_in_user, follow_author))
        else:
            cursor.execute("INSERT INTO followers (follower_username, following_author, date_followed) VALUES (%s, %s, %s)",
                           (logged_in_user, follow_author, date.today()))
        conn.commit()
        return redirect('profilefollower', username=username)

    # Get followers of the author
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username = %s THEN TRUE 
            ELSE FALSE 
        END as is_following
        FROM followers f
        JOIN register r ON f.follower_username = r.username
        LEFT JOIN followers f2 
            ON f2.follower_username = %s 
           AND f2.following_author = r.username
        WHERE f.following_author = %s
    """, (logged_in_user, logged_in_user, username))

    followers = cursor.fetchall()

    # Convert BLOB to Base64
    for follower in followers:
        if follower['profilephoto']:
            follower['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(follower['profilephoto']).decode('utf-8')
        else:
            follower['profilephoto'] = "/static/images/default.png"

    conn.close()

    return render(request, 'blog/profilefollower.html', {
        'followers': followers,
        'author_username': username
    })

from django.http import JsonResponse


def toggle_follow(request):
    if request.method == "POST" and request.session.get('username'):
        logged_in_user = request.session['username']
        follow_author = request.POST.get('follow_author')

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="blogposts"
        )
        cursor = conn.cursor(dictionary=True)

        # Check if already following
        cursor.execute("SELECT * FROM followers WHERE follower_username=%s AND following_author=%s",
                       (logged_in_user, follow_author))
        existing = cursor.fetchone()

        if existing:
            # Unfollow
            cursor.execute("DELETE FROM followers WHERE follower_username=%s AND following_author=%s",
                           (logged_in_user, follow_author))
            conn.commit()
            status = "unfollowed"
        else:
            # Follow
            cursor.execute("INSERT INTO followers (follower_username, following_author, date_followed) VALUES (%s, %s, %s)",
                           (logged_in_user, follow_author, date.today()))
            conn.commit()
            status = "followed"
        cursor.close()
        conn.close()
        return JsonResponse({'status': status})
    return JsonResponse({'status': 'error'}, status=400)

from django.http import JsonResponse
from datetime import datetime

from django.http import JsonResponse
import mysql.connector
from datetime import date, datetime

def toggle_like(request):
    if request.method == "POST" and request.session.get('username'):
        username = request.session['username']
        post_title = request.POST.get('post_title')

        conn = mysql.connector.connect(host="localhost", user="root", password="", database="blogposts")
        cursor = conn.cursor(dictionary=True)

        # Check if already liked
        cursor.execute("SELECT * FROM likes WHERE username=%s AND post_title=%s", (username, post_title))
        existing = cursor.fetchone()

        if existing:
            # Unlike
            cursor.execute("DELETE FROM likes WHERE username=%s AND post_title=%s", (username, post_title))
            is_liked = False
        else:
            # Like
            cursor.execute("INSERT INTO likes (username, post_title) VALUES (%s, %s)", (username, post_title))
            is_liked = True

        # Get updated count from likes table
        cursor.execute("SELECT COUNT(*) AS total FROM likes WHERE post_title=%s", (post_title,))
        total_likes = cursor.fetchone()['total']

        # Update the postcreation table
        cursor.execute("UPDATE postcreation SET likes = %s WHERE title = %s", (total_likes, post_title))

        conn.commit()
        conn.close()

        return JsonResponse({'status': 'liked' if is_liked else 'unliked', 'likes': total_likes})
    
    return JsonResponse({'status': 'error'}, status=400)

def add_comment(request):
    if request.method == "POST" and request.session.get('username'):
        username = request.session['username']
        post_title = request.POST.get('post_title')
        comment_text = request.POST.get('comment')
        now = datetime.now()

        conn = mysql.connector.connect(host="localhost", user="root", password="", database="blogposts")
        cursor = conn.cursor()

        cursor.execute("INSERT INTO comments (post_title, commenter, comment, date, time) VALUES (%s, %s, %s, %s, %s)",
                       (post_title, username, comment_text, now.date(), now.strftime("%H:%M")))
        conn.commit()
        conn.close()

        return JsonResponse({
            'commenter': username,
            'comment': comment_text,
            'date': str(now.date()),
            'time': now.strftime("%H:%M")
        })


