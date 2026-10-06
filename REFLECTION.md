## Featured Products.
Question 1 - Trace the feature. Explain how marking a product as featured in the admin interface causes the badge to appear in the storefront. Explain the files involved and the code logic. Marking a product as featured reflects on the product row where other templates check. It starts from products/model.py checking if a product is featured or not, where it then goes into checking the admin ModelForm to see if it has changed and where the templates read it and make changes to their UI.

Question 2 - How you verified it. Describe how you confirmed the feature works. Name the pages you checked in the browser. I confirmed the feature works by checking each product through the product page and checking their description to see if the featured tag was there.

Question 3 - Judgement. Describe one challenge, unexpected result, or edge case you encountered. Explain what you did to troubleshoot it. One challenge that I came across was making sure the migration was properly implemented due to claude immediately migrating without asking for permission. I troubleshooted it by manually checking the file and running test code to make sure the code properly worked. 

## Discount Coupons
Question 1 - One decision from grill me. Choose one /grill-me question that led to an important design decision. If you disagreed with the agent's recommendation, explain what it recommended, why you rejected that recommendation, what you chose instead, and how your choice affected the feature. If you did not disagree with any recommendation, choose a question that was confusing. Explain what you did not understand, the follow-up question(s) you asked, and how you ultimately decided.
The most confusing question was question 9 about revenue. It took me a while to understand that it was asking about showing the total instead of a breakdown per item from the discount. I ultimately decide with the recommendation because it showed the easiest way for the staff to tell how much a promotion cost.

Question 2 - The change. Explain the change you made after reviewing the feature. Describe your original choice, what the browser showed you, why you wanted to change it, and how the fix works. If any existing test failed during your build, name it and say what you did about it.
My original choice was to have the codes be random strings of letters. Upon being showed the codes, it felt awkward and not professional and had the codes changed to be actual words instead of random letters.

## Product Images
Question 1 - One decision from grill me. Choose one /grill-me question that led to an important design decision. If you disagreed with the agent's recommendation, explain what it recommended, why you rejected that recommendation, what you chose instead, and how your choice affected the feature. If you did not disagree with any recommendation, choose a question that was confusing. Explain what you did not understand, the follow-up question(s) you asked, and how you ultimately decided.
The question that was confusing was the one about making a server side checker for the images, where I had to realize that making a server side checker was more reliable in order to make sure no broken image symbols appeared.

Question 2 - Find the upload code.
Find the ImageField the agent added to the Product model. Copy that line into your answer and include the filename and line number. Explain what the upload_to value does. image = models.ImageField(upload_to=product_image_path, blank=True) in products/models.py on line 98. The upload_to value shows django where to save an uploaded file and what it's name should be. 

Find the <form> used to upload a product image. Copy the opening <form> tag into your answer and include the filename and line number. Explain why enctype is needed for a file upload. 
<form hx-post="{% url 'products:manage_product_image' product.pk %}"
      hx-encoding="multipart/form-data"
      hx-target="#product-image"
      hx-swap="outerHTML"
      class="space-y-3">
in the file templates/prudicts/partials/_product_image.html on lines 18 through 22. Enctype is needed to tell the browser how to put data and text into a HTTP request without any errors or corruption.

Question 3 - Follow the upload process. Your invented product's image is stored somewhere on disk and served from some URL. Follow the image for the product you created through the application and write:
The path where the image file is stored on disk.
The value stored in the database for that image.
The URL the browser requests to display it.
For each one, name the Django field or setting that determines it and the file where that field or setting is defined. Finally, explain what code makes the media URL work while you run the development server. If you cannot find one of these, ask the agent, check the code, confirm your understanding, and write it up in your own words.
C:\Users\efurm\Desktop\ADV BUS PROGRAM\thoughttronix-store\media\products\CyVisor-rl1u0t.webp is the path to where the image is stored on disk. 
products/CyVisor-rl1u0t.webp is the value stored in the database for the image
http://127.0.0.1:8000/media/products/CyVisor-rl1u0t.webp is the URL the browser requests in order to display it. 
The code that makes the URL work while running the server is urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT).