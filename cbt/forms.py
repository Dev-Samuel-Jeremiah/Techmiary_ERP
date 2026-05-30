from django import forms
from .models import Exam

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = '__all__'  # or list fields you want editable


from django import forms

class BulkQuestionUploadForm(forms.Form):
    exam_part = forms.IntegerField()
    file = forms.FileField(
        help_text="Upload CSV or Excel file (.csv, .xlsx)"
    )
