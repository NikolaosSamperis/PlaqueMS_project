from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone
from datetime import timedelta

# Create your models here.
from django.db import models


# Create your models here.
# proteins
class Proteins(models.Model):
    protein_id = models.CharField('protein_id', primary_key=True, max_length=50, default="")
    uniprot_accession_id = models.CharField('uniprot_accession_id', max_length=50, default="")
    uniprotkb_id = models.CharField('uniprotkb_id', max_length=64, default="")
    gene_name = models.CharField('gene_name', max_length=64, default="")

    class Meta:
        db_table = 'proteins'


class Datasets(models.Model):
    dataset_id = models.CharField('dataset_id', primary_key=True, max_length=50)
    name = models.CharField('name', max_length=100, default="")
    position = models.CharField('position', max_length=250, default="")
    description = models.CharField('description', max_length=100, null=True)

    class Meta:
        db_table = 'datasets'



class Networks(models.Model):
    network_id = models.CharField('network_id', primary_key=True, max_length=50)
    filename = models.CharField('filename', max_length=100, default="")
    filepath = models.CharField('filepath', max_length=255, default="")
    description = models.CharField('description', max_length=100, null=True)

    class Meta:
        db_table = 'networks'


class Statistics(models.Model):
    doc_id = models.CharField('doc_id', primary_key=True, max_length=50)
    filename = models.CharField('filename', max_length=100, default="")
    filepath = models.CharField('filepath', max_length=255, default="")
    doc_type = models.CharField('doc_type', max_length=5, default="")
    label = models.CharField('label', max_length=5, default="")

    class Meta:
        db_table = 'statistics'


class ExperimentsTypes(models.Model):
    experiment_id = models.CharField('experiment_id', primary_key=True, max_length=50)
    pathname = models.CharField('pathname', max_length=100)
    path_type = models.CharField('path_type', max_length=10)
    path = models.CharField('path', max_length=255)
    parent_id = models.CharField('parent_id', max_length=50)
    dataset_id = models.CharField('dataset_id', max_length=50)

    class Meta:
        db_table = 'experiments_types'



class DocAndExperiment(models.Model):
    id = models.CharField('id', primary_key=True, max_length=50)
    experiment_id = models.CharField('experiment_id', max_length=50)
    doc_id = models.CharField('doc_id', max_length=50)

    class Meta:
        db_table = 'doc_and_experiment'


class NetworkAndExperiment(models.Model):
    id = models.CharField('id', primary_key=True, max_length=50)
    experiment_id = models.CharField('experiment_id', max_length=50)
    network_id = models.CharField('network_id', max_length=50)

    class Meta:
        db_table = 'network_and_experiment'


class DiffResult(models.Model):
    doc_id = models.CharField('doc_id', primary_key=True, max_length=50)
    filename = models.CharField('filename', max_length=100, default="")
    filepath = models.CharField('filepath', max_length=255, default="")
    network_id = models.CharField('network_id', max_length=50)

    class Meta:
        db_table = 'diff_result'


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        # Create the user without requiring a username.
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
            
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=30)
    last_name = models.CharField(_('last name'), max_length=30)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_users', db_column='approved_by_id')
    approved_at = models.DateTimeField(null=True, blank=True)
    registration_time = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    class Meta:
        db_table = 'login_customuser'
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"