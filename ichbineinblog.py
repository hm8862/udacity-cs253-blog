#Udacity CS253 Blog app

import os, sys, time, logging
import webapp2
import jinja2
import re
import hmac
import utilities
from google.appengine.ext import db
from google.appengine.api import memcache

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape=True)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class BlogHandler(webapp2.RequestHandler):

    #quick write function
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
    
    #print template
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

class MainPage(BlogHandler):
    def get(self):
        """# .all() notation from Google GQL procedural language - could us SQL here
        posts = Post.all().order('-created')
        #posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC") #GQL alternative
        self.render('front.html', posts = posts)"""
        
        self.response.headers['Content-Type'] = 'text/plain'
        visits = 0
        visit_cookie_str = self.request.cookies.get('visits')
        if visit_cookie_str:
                cookie_val = utilities.check_secure_val(visit_cookie_str)
                if cookie_val:
                        visits = int(cookie_val)

        visits += 1

        new_cookie_val = utilities.make_secure_val(str(visits))

        self.response.headers.add_header('Set-Cookie', 'visits=%s' % new_cookie_val)

        if visits > 100:
                self.write("You are the best ever!")
        else:
                self.write("You've been here %s times!" % visits)

##### Blog stuff here - try and delete any unnecessary BS.

#assigns parent "blog" key
#def blog_key(name = 'default'):
#    return db.Key.from_path('blogs', name)

#define database object for storing blog posts
class Post(db.Model):
    #define blog post properties in database
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)

    def render(self):
        #preserve whitespace and render blog post
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", p = self)

start = time.time()

def get_posts(update = False):
    key = 'blog_front'
    posts = memcache.get(key)

    if posts is None or update:
        global start
        start = time.time()
        logging.error("DB QUERY")
        posts = Post.all().order('-created')
        posts = list(posts)
        memcache.set(key, posts)

    return posts, time.time() - start


#blog front page
class BlogFront(BlogHandler):
    def get(self):
        # .all() notation from Google GQL procedural language - could us SQL here
        #key = 'blog_front'
        #posts = memcache.get(key)
        #if posts is None
        #posts = Post.all().order('-created') #.fetch(10)
        posts, times = get_posts()

        #posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC") #GQL alternative
        self.render("front.html", posts = posts, time = times)

#blog front page in json
class BlogFrontJson(BlogHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
        posts = Post.all().order('-created') #.fetch(10)
        p = list(posts)
        j = utilities.build_json(p, len(p))
        self.write(j)

#render users
class RenderUsers(BlogHandler):
    def get(self):
        users = User.all()
        self.response.headers['Content-Type'] = 'text/plain'
        for u in users:
            self.write(u.created)#"%s | %s | %s \n" % (u.user_name, u.created, u.key().id()))

permalink_start = time.time()

def get_permalink_post(post_id, update = False):
    key = '%s' % post_id
    post = memcache.get(key)

    if post is None or update:
        global permalink_start
        permalink_start = time.time()
        logging.error("DB QUERY")
        db_key = db.Key.from_path('Post', int(post_id), parent = utilities.blog_key())
        post = db.get(db_key)
        memcache.set(key, (post, permalink_start))
        return post, time.time() - permalink_start
    else:
        return post[0], time.time() - post[1]

class FlushCache(BlogHandler):
    def get(self):
        memcache.flush_all()
        global start
        start = time.time()
        global permalink_start
        permalink_start = time.time()
        self.redirect('/blog')

#individual blog post page
class PostPage(BlogHandler):
    def get(self, post_id): #note: post_id is a parameter passed by the URL handler, by parenthesising the regular expression you are declaring that this is a variable that should be passed into the PostPage handler
        #key = db.Key.from_path('Post', int(post_id), parent = utilities.blog_key())
        #post = db.get(key)
        post, time = get_permalink_post(post_id)
        if not post:
            self.error(404)
            return

        get_posts(True)
        self.render('permalink.html', post = post, time = time)

#return individual blog post as json
class PostPageJson(BlogHandler):
    def get(self, post_id):
        self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
        key = db.Key.from_path('Post', int(post_id), parent = utilities.blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        self.write(utilities.build_json(post, 1))

class NewPost(BlogHandler):
    def get(self):
        self.render("newpost.html")

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post(parent = utilities.blog_key(), subject = subject, content = content)
            p.put() #write to database
            post_id = str(p.key().id())
            get_permalink_post(post_id, True)
            self.redirect('/blog/%s' % post_id)
        else:
            error = "subject and content, please!"
            self.render("newpost.html", subject = subject, content = content, error = error)

#User database object
class User(db.Model):
    #define blog post properties in database
    user_name = db.StringProperty(required = True)
    password_hash = db.TextProperty(required = True)
    email_address = db.TextProperty(required = False)
    #salt = db.DateTimeProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_active = db.DateTimeProperty(auto_now = True)

class unit_3_signup(BlogHandler):
    def get(self):
        self.render("signup.html", username="", user_error="", password="", 
                                                    password_error="", 
                                                    verify="",
                                                    verify_error="", 
                                                    email="",
                                                    email_error="")

    def post(self):
        #self.response.headers['Content-Type'] = 'text/plain'

        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')
        user_check = User.gql('WHERE user_name=:1', username).get()

        params = dict(username = username,
                      email = email)

        if not utilities.valid_username(username):
            params['user_error'] = "That's not a valid username."
            have_error = True

        if not utilities.valid_password(password):
            params['password_error'] = "That wasn't a valid password."
            have_error = True
        elif password != verify:
            params['verify_error'] = "Your passwords didn't match."
            have_error = True

        if email and not utilities.valid_email(email):
            params['email_error'] = "That's not a valid email."
            have_error = True

        if user_check:
            params['user_error'] = "User already exists"
            have_error = True
       
        if have_error:
            self.render('signup.html', **params)
        else:
            if email:
                user = User(parent = utilities.blog_key(), user_name = username,
                                                password_hash = utilities.hash_str(password))
            else:
                user = User(parent = utilities.blog_key(), user_name = username,
                                                    password_hash = utilities.hash_str(password),
                                                    email_address = email)
            user.put()
            user_id = user.key().id()
            id_hash = utilities.hash_str(str(user_id))
            self.response.headers.add_header('Set-Cookie', 'user_id=%s|%s; Path=/' % (str(user_id), str(id_hash)))
            self.redirect('/blog/welcome')

class unit_3_welcome(BlogHandler):
    def get(self):
        cookie = self.request.cookies.get("user_id")
        user = utilities.check_user(cookie)
        
        #validate user and cookie
        if user:
            self.render('welcome.html', username = user.user_name)
        else:
            self.redirect('signup')

class login(BlogHandler):
    def get(self):
        self.render("login.html", username="", user_error="", password="", 
                                                    password_error="")

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        user_check = User.gql('WHERE user_name=:1', username).get()
        password_hash = utilities.hash_str(password)

        #if user exists and password correct, set cookie, else return error
        params = dict(username = username)
        
        if not username or not password:
            params['error'] = "Invalid login"
            self.render('login.html', **params)
        else:
            if user_check and password_hash == user_check.password_hash:
                user_id = user_check.key().id()    
                id_hash = utilities.hash_str(str(user_id))
                self.response.headers.add_header('Set-Cookie', 'user_id=%s|%s; Path=/' % (str(user_id), str(id_hash)))
                self.redirect('/blog/welcome')
            else:
                params['error'] = "Invalid login"
                self.render('login.html', **params)

class logout(BlogHandler):
    def get(self):
        self.response.delete_cookie('user_id')
        self.redirect('/blog/signup')

class signup(BlogHandler):

    def get(self):
        self.render("signup.html", username="", user_error="", password="", 
                                                    password_error="", 
                                                    verify="",
                                                    verify_error="", 
                                                    email="",
                                                    email_error="")

    def post(self):
        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        params = dict(username = username,
                      email = email)

        if not valid_username(username):
            params['user_error'] = "That's not a valid username."
            have_error = True

        if not valid_password(password):
            params['password_error'] = "That wasn't a valid password."
            have_error = True
        elif password != verify:
            params['verify_error'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(email):
            params['email_error'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render('signup-form.html', **params)
        else:
            self.redirect('/unit2/welcome?username=' + username)

class Welcome(BlogHandler):
    def get(self):
        username = self.request.get('username')
        if validate_username(username):
            self.render('welcome.html', username = username)
        else:
            self.redirect('/signup')

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/blog/newpost/?', NewPost),
    ('/blog/?', BlogFront),
    ('/blog/([0-9]+)', PostPage),
    ('/signup/?', signup),
    ('/welcome/?', Welcome),
    ('/blog/signup/?', unit_3_signup),
    ('/blog/welcome/?', unit_3_welcome),
    ('/users', RenderUsers),
    ('/blog/login/?', login),
    ('/blog/logout/?', logout),
    ('/blog/([0-9]+).json', PostPageJson),
    ('/blog/.json', BlogFrontJson),
    ('/blog/flush/?', FlushCache)
], debug=True)
