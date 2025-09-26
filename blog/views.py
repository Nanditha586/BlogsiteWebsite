import sqlite3
from datetime import date, datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
import base64

from .models import BlogPost, Post
from .forms import BlogPostForm

DB_PATH = "db.sqlite3"  # SQLite database path

# Utility function to convert sqlite rows to dict
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# Connect to SQLite
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

# Home page view
def home(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'blog/home.html', {'posts': posts})

# Post detail page
def post_detail(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    return render(request, 'blog/post_detail.html', {'post': post})

# User Registration
def registerview(request):
    if request.method == "POST":
        username = request.POST.get('username')
        phonenumber = request.POST.get('phonenumber')
        email = request.POST.get('email')
        password = request.POST.get('password')
        profilephoto = request.FILES.get('profilephoto')
        bio = request.POST.get('bio')

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM register WHERE email = ?", (email,))
        email_exists = cursor.fetchone()
        cursor.execute("SELECT * FROM register WHERE username = ?", (username,))
        username_exists = cursor.fetchone()

        if email_exists:
            messages.error(request, "⚠️ Email already exists! Please use another email.")
            conn.close()
            return redirect('register')
        elif username_exists:
            messages.error(request, "⚠️ Username already exists! Please choose another username.")
            conn.close()
            return redirect('register')
        else:
            photo_data = profilephoto.read() if profilephoto else None
            cursor.execute(
                "INSERT INTO register (username, phonenumber, email, password, profilephoto) VALUES (?, ?, ?, ?, ?)",
                (username, phonenumber, email, password, photo_data)
            )
            conn.commit()
            conn.close()
            messages.success(request, "Registered successfully! You can login now.")
            return redirect('register')
    else:
        return render(request, 'blog/register.html')

# User Login
def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM register WHERE email = ? AND password = ?", (email, password))
        result = cursor.fetchone()
        conn.close()

        if result:
            request.session['email'] = result['email']
            request.session['username'] = result['username']
            return redirect('posts')
        else:
            messages.error(request, "❌ Invalid credentials")
            return render(request, "blog/login.html")
    else:
        return render(request, 'blog/login.html')

def logout(request):
    try:
        # Remove email from session if exists
        if('email' in request.session):
             del request.session["email"]
    except KeyError:
        pass
    return redirect('login')
# Create a new blog post
def create_post(request):
    if not request.session.get('email'):
        messages.error(request, "⚠️ Please login to create a post.")
        return redirect('login')

    username = request.session.get('username')

    if request.method == "POST":
        title = request.POST.get('title')
        category = request.POST.get('category')
        content = request.POST.get('content')
        date_value = request.POST.get('date')
        time_value = request.POST.get('time')
        blogphoto = request.FILES.get('blogphoto')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM postcreation WHERE title = ?", (title,))
        result = cursor.fetchone()

        if result:
            conn.close()
            messages.error(request, "⚠️ Title already exists! Please choose another title.")
            return redirect('create_post')
        else:
            image_data = blogphoto.read() if blogphoto else None
            cursor.execute(
                "INSERT INTO postcreation (title, category, content, blogphoto, author, date, time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, category, content, image_data, username, date_value, time_value)
            )
            conn.commit()
            conn.close()
            messages.success(request, "✅ Post added successfully!")
            return redirect('create_post')

    return render(request, 'blog/create_post.html', {'username': username})

# Show all posts
def posts(request):
    page_number = request.GET.get('page', 1)
    selected_categories = request.GET.getlist('categories')
    search_query = request.GET.get('q', '')

    conn = get_connection()
    cursor = conn.cursor()
    post_modal_to_open = None

    # Handle POST actions
    if request.method == "POST" and request.session.get('email'):
        username = request.session.get('username')

        if 'comment' in request.POST:
            comment_text = request.POST.get('comment')
            post_title = request.POST.get('post_title')
            today = date.today()
            now = datetime.now().strftime("%H:%M:%S")
            if comment_text.strip():
                cursor.execute(
                    "INSERT INTO comments (post_title, commenter, comment, date, time) VALUES (?, ?, ?, ?, ?)",
                    (post_title, username, comment_text, today, now)
                )
                conn.commit()
        elif 'like_post' in request.POST:
            post_title = request.POST.get('like_post')
            cursor.execute("SELECT * FROM likes WHERE post_title=? AND username=?", (post_title, username))
            already_liked = cursor.fetchone()
            if not already_liked:
                cursor.execute("INSERT INTO likes (post_title, username) VALUES (?, ?)", (post_title, username))
                cursor.execute("UPDATE postcreation SET likes = likes + 1 WHERE title=?", (post_title,))
            else:
                cursor.execute("DELETE FROM likes WHERE post_title=? AND username=?", (post_title, username))
                cursor.execute("UPDATE postcreation SET likes = likes - 1 WHERE title=? AND likes > 0", (post_title,))
            conn.commit()
        elif 'follow_author' in request.POST:
            author_to_follow = request.POST.get('follow_author')
            cursor.execute("SELECT * FROM followers WHERE follower_username=? AND following_author=?",
                           (username, author_to_follow))
            already_following = cursor.fetchone()
            if not already_following:
                cursor.execute(
                    "INSERT INTO followers (follower_username, following_author, date_followed) VALUES (?, ?, ?)",
                    (username, author_to_follow, date.today()))
            else:
                cursor.execute(
                    "DELETE FROM followers WHERE follower_username=? AND following_author=?",
                    (username, author_to_follow))
            conn.commit()

    # Fetch posts with optional search and category filter
    query = "SELECT p.title, p.content, p.blogphoto, p.author, p.date, p.time, p.likes, r.profilephoto, p.category " \
            "FROM postcreation p JOIN register r ON p.author = r.username WHERE 1=1 "
    params = []
    if search_query:
        query += "AND (p.title LIKE ? OR p.author LIKE ? OR p.date LIKE ? OR p.category LIKE ?) "
        params.extend(['%' + search_query + '%'] * 4)
    if selected_categories:
        query += "AND p.category IN ({}) ".format(",".join("?" * len(selected_categories)))
        params.extend(selected_categories)
    query += "ORDER BY p.date DESC, p.time DESC"
    cursor.execute(query, params)
    all_posts = cursor.fetchall()

    # Convert images and fetch comments
    for post in all_posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
        if post['profilephoto']:
            post['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(post['profilephoto']).decode('utf-8')
        else:
            post['profilephoto'] = "/static/images/default.png"

        cursor.execute(
            "SELECT commenter, comment, date, time FROM comments WHERE post_title=? ORDER BY date DESC, time DESC",
            (post['title'],))
        post['comments'] = cursor.fetchall()

        if request.session.get('email'):
            username = request.session.get('username')
            cursor.execute("SELECT 1 FROM likes WHERE post_title=? AND username=?", (post['title'], username))
            post['is_liked'] = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM followers WHERE follower_username=? AND following_author=?",
                           (username, post['author']))
            post['is_following'] = cursor.fetchone() is not None
        else:
            post['is_liked'] = False
            post['is_following'] = False

    conn.close()
    paginator = Paginator(all_posts, 6)
    page_obj = paginator.get_page(page_number)

    return render(request, 'blog/posts.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_categories': selected_categories,
        'post_modal_to_open': post_modal_to_open,
    })

# The rest of your views (profilepage, edit_profile, myposts, edit_myposts, delete_myposts, aboutauthor, followers, following, profilefollowing, profilefollower, toggle_follow, toggle_like, add_comment) 
# follow the same pattern: replace MySQL connections with `get_connection()`, use `?` placeholders, use `dict_factory` to fetch dictionaries.

# Profile page
def profilepage(request, username):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM register WHERE username=?", (username,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT * FROM postcreation WHERE author=? ORDER BY date DESC, time DESC", (username,))
    posts = cursor.fetchall()
    
    # Convert profile and post images
    if user['profilephoto']:
        user['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(user['profilephoto']).decode('utf-8')
    else:
        user['profilephoto'] = "/static/images/default.png"
    
    for post in posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
    
    # Followers and following counts
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE following_author=?", (username,))
    followers_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE follower_username=?", (username,))
    following_count = cursor.fetchone()['count']
    
    conn.close()
    return render(request, 'blog/profilepage.html', {
        'user': user,
        'posts': posts,
        'followers_count': followers_count,
        'following_count': following_count
    })

# Edit profile
def edit_profile(request, username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM register WHERE username=?", (username,))
    user = cursor.fetchone()
    
    if request.method == "POST":
        phonenumber = request.POST.get('phonenumber')
        bio = request.POST.get('bio')
        profilephoto = request.FILES.get('profilephoto')
        photo_data = profilephoto.read() if profilephoto else user['profilephoto']
        
        cursor.execute("UPDATE register SET phonenumber=?, bio=?, profilephoto=? WHERE username=?",
                       (phonenumber, bio, photo_data, username))
        conn.commit()
        conn.close()
        messages.success(request, "✅ Profile updated successfully!")
        return redirect('profilepage', username=username)
    
    conn.close()
    return render(request, 'blog/edit_profile.html', {'user': user})

# My posts
def myposts(request):
    if not request.session.get('email'):
        return redirect('login')
    
    username = request.session.get('username')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM postcreation WHERE author=? ORDER BY date DESC, time DESC", (username,))
    posts = cursor.fetchall()
    
    for post in posts:
        if post['blogphoto']:
            post['blogphoto'] = "data:image/jpeg;base64," + base64.b64encode(post['blogphoto']).decode('utf-8')
    
    conn.close()
    return render(request, 'blog/myposts.html', {'posts': posts})

# Edit my post
def edit_myposts(request, post_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM postcreation WHERE id=?", (post_id,))
    post = cursor.fetchone()
    
    if request.method == "POST":
        title = request.POST.get('title')
        category = request.POST.get('category')
        content = request.POST.get('content')
        blogphoto = request.FILES.get('blogphoto')
        photo_data = blogphoto.read() if blogphoto else post['blogphoto']
        
        cursor.execute("UPDATE postcreation SET title=?, category=?, content=?, blogphoto=? WHERE id=?",
                       (title, category, content, photo_data, post_id))
        conn.commit()
        conn.close()
        messages.success(request, "✅ Post updated successfully!")
        return redirect('myposts')
    
    conn.close()
    return render(request, 'blog/edit_myposts.html', {'post': post})

# Delete my post
def delete_myposts(request, post_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM postcreation WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    messages.success(request, "✅ Post deleted successfully!")
    return redirect('myposts')

# About author modal data (AJAX)
def aboutauthor(request):
    post_title = request.GET.get('post_title')
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM postcreation WHERE title=?", (post_title,))
    post = cursor.fetchone()
    author = post['author']
    
    cursor.execute("SELECT * FROM register WHERE username=?", (author,))
    author_data = cursor.fetchone()
    
    if author_data['profilephoto']:
        author_data['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(author_data['profilephoto']).decode('utf-8')
    
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE following_author=?", (author,))
    followers_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE follower_username=?", (author,))
    following_count = cursor.fetchone()['count']
    
    conn.close()
    return JsonResponse({
        'author': author_data['username'],
        'bio': author_data.get('bio', ''),
        'profilephoto': author_data['profilephoto'],
        'followers_count': followers_count,
        'following_count': following_count
    })

# Followers page
def followers(request, username):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT r.username, r.profilephoto FROM followers f JOIN register r ON f.follower_username = r.username WHERE f.following_author=?",
        (username,))
    followers_list = cursor.fetchall()
    
    for user in followers_list:
        if user['profilephoto']:
            user['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(user['profilephoto']).decode('utf-8')
        else:
            user['profilephoto'] = "/static/images/default.png"
    
    conn.close()
    return render(request, 'blog/followers.html', {'followers': followers_list})

# Following page
def following(request, username):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT r.username, r.profilephoto FROM followers f JOIN register r ON f.following_author = r.username WHERE f.follower_username=?",
        (username,))
    following_list = cursor.fetchall()
    
    for user in following_list:
        if user['profilephoto']:
            user['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(user['profilephoto']).decode('utf-8')
        else:
            user['profilephoto'] = "/static/images/default.png"
    
    conn.close()
    return render(request, 'blog/following.html', {'following': following_list})

# Toggle follow/unfollow AJAX
def toggle_follow(request):
    if request.method == "POST" and request.session.get('email'):
        follower = request.session.get('username')
        following_author = request.POST.get('author')
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM followers WHERE follower_username=? AND following_author=?",
                       (follower, following_author))
        exists = cursor.fetchone()
        if exists:
            cursor.execute("DELETE FROM followers WHERE follower_username=? AND following_author=?",
                           (follower, following_author))
            action = "unfollowed"
        else:
            cursor.execute("INSERT INTO followers (follower_username, following_author, date_followed) VALUES (?, ?, ?)",
                           (follower, following_author, date.today()))
            action = "followed"
        conn.commit()
        conn.close()
        return JsonResponse({'status': action})
    return JsonResponse({'status': 'error'})

# Toggle like/unlike AJAX
def toggle_like(request):
    if request.method == "POST" and request.session.get('email'):
        username = request.session.get('username')
        post_title = request.POST.get('post_title')
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM likes WHERE post_title=? AND username=?", (post_title, username))
        exists = cursor.fetchone()
        if exists:
            cursor.execute("DELETE FROM likes WHERE post_title=? AND username=?", (post_title, username))
            cursor.execute("UPDATE postcreation SET likes = likes - 1 WHERE title=? AND likes > 0", (post_title,))
            action = "unliked"
        else:
            cursor.execute("INSERT INTO likes (post_title, username) VALUES (?, ?)", (post_title, username))
            cursor.execute("UPDATE postcreation SET likes = likes + 1 WHERE title=?", (post_title,))
            action = "liked"
        conn.commit()
        cursor.execute("SELECT likes FROM postcreation WHERE title=?", (post_title,))
        likes_count = cursor.fetchone()['likes']
        conn.close()
        return JsonResponse({'status': action, 'likes_count': likes_count})
    return JsonResponse({'status': 'error'})

# Add comment AJAX
def add_comment(request):
    if request.method == "POST" and request.session.get('email'):
        username = request.session.get('username')
        post_title = request.POST.get('post_title')
        comment_text = request.POST.get('comment')
        today = date.today()
        now = datetime.now().strftime("%H:%M:%S")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comments (post_title, commenter, comment, date, time) VALUES (?, ?, ?, ?, ?)",
                       (post_title, username, comment_text, today, now))
        conn.commit()
        cursor.execute("SELECT commenter, comment, date, time FROM comments WHERE post_title=? ORDER BY date DESC, time DESC",
                       (post_title,))
        comments = cursor.fetchall()
        conn.close()
        return JsonResponse({'comments': comments})
    return JsonResponse({'status': 'error'})

def profilefollowing(request, username):
    if not request.session.get('username'):
        return redirect('login')

    logged_in_user = request.session['username']

    conn = get_connection()  # SQLite connection with dict_factory
    cursor = conn.cursor()

    # Handle follow/unfollow toggle
    if request.method == "POST":
        follow_author = request.POST.get('follow_author')
        cursor.execute(
            "SELECT * FROM followers WHERE follower_username=? AND following_author=?",
            (logged_in_user, follow_author)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "DELETE FROM followers WHERE follower_username=? AND following_author=?",
                (logged_in_user, follow_author)
            )
        else:
            cursor.execute(
                "INSERT INTO followers (follower_username, following_author, date_followed) VALUES (?, ?, ?)",
                (logged_in_user, follow_author, date.today())
            )
        conn.commit()
        return redirect('profilefollowing', username=username)

    # Get list of people the author is following
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username IS NOT NULL THEN 1
            ELSE 0
        END as is_following
        FROM followers f
        JOIN register r ON f.following_author = r.username
        LEFT JOIN followers f2
            ON f2.follower_username = ?
           AND f2.following_author = r.username
        WHERE f.follower_username = ?
    """, (logged_in_user, username))

    following = cursor.fetchall()

    # Convert BLOB to Base64
    for person in following:
        if person['profilephoto']:
            person['profilephoto'] = "data:image/jpeg;base64," + base64.b64encode(person['profilephoto']).decode('utf-8')
        else:
            person['profilephoto'] = "/static/images/default.png"

    conn.close()

    return render(request, 'blog/profilefollowing.html', {
        'following': following,
        'author_username': username
    })


def profilefollower(request, username):
    if not request.session.get('username'):
        return redirect('login')

    logged_in_user = request.session['username']

    conn = get_connection()  # SQLite connection with dict_factory
    cursor = conn.cursor()

    # Handle follow/unfollow POST
    if request.method == "POST":
        follow_author = request.POST.get('follow_author')
        cursor.execute(
            "SELECT * FROM followers WHERE follower_username=? AND following_author=?",
            (logged_in_user, follow_author)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "DELETE FROM followers WHERE follower_username=? AND following_author=?",
                (logged_in_user, follow_author)
            )
        else:
            cursor.execute(
                "INSERT INTO followers (follower_username, following_author, date_followed) VALUES (?, ?, ?)",
                (logged_in_user, follow_author, date.today())
            )
        conn.commit()
        return redirect('profilefollower', username=username)

    # Get followers of the author
    cursor.execute("""
        SELECT r.username, r.profilephoto,
        CASE 
            WHEN f2.follower_username IS NOT NULL THEN 1
            ELSE 0
        END as is_following
        FROM followers f
        JOIN register r ON f.follower_username = r.username
        LEFT JOIN followers f2
            ON f2.follower_username = ?
           AND f2.following_author = r.username
        WHERE f.following_author = ?
    """, (logged_in_user, username))

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
