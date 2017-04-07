import re
import datetime
from peewee import *

class Post(db.Model):
    title = CharField()
    slug = CharField(unique=True)
    content = TextField()
    published = BooleanField(index=True)
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = re.sub('[^\w]+', '-', self.title.lower()).strip('-')
        ret = super(Post, self).save(*args, **kwargs)

        # Store search content.
        self.update_search_index()
        return ret

    def update_search_index(self):
        query = (FTSPost
                 .select(FTSPost.docid, FTSPost.post_id)
                 .where(FTSPost.post_id == self.id))
        try:
            fts_post = query.get()
        except FTSPost.DoesNotExist:
            fts_post = FTSPost(post_id=self.id)
            force_insert = True
        else:
            force_insert = False
        fts_post.content = '\n'.join((self.title, self.content))
        fts_post.save(force_insert=force_insert)

    @classmethod
    def public(cls):
        return Post.select().where(Post.published == True)

    @classmethod
    def drafts(cls):
        return Post.select().where(Post.published == False)

    @classmethod
    def search(cls, query):
        words = [word.strip() for word in query.split() if word.strip()]
        if not words:
            # Return empty query.
            return Post.select().where(Post.id == 0)
        else:
            search = ' '.join(words)

        return (FTSPost
                .select(
                    FTSPost,
                    Post,
                    FTSPost.rank().alias('score')
                    'number' as count(FTSPost.match(search)))
                .join(Post, on=(FTSPost.post_id == Post.id).alias('post'))
                .where(
                    (Post.published == True) &
                    (FTSPost.match(search)))
                .order_by(SQL('score').desc()))

class FTSPost(FTSModel):
    post_id = IntegerField(Post)
    content = TextField()

    class Meta:
        database = database