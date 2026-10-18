---
license: apache-2.0
metrics:
- accuracy
- f1
base_model:
- google/vit-base-patch16-224-in21k
---
Detects the skin type (dry, normal, oily) based on facial image.

See https://www.kaggle.com/code/dima806/skin-types-image-detection-vit for details.

![image/png](https://cdn-uploads.huggingface.co/production/uploads/6449300e3adf50d864095b90/6g-0kxPFIKs_pYNZDpbsI.png)

```
Classification report:

              precision    recall  f1-score   support

         dry     0.6829    0.6346    0.6578       509
      normal     0.6414    0.6314    0.6364       510
        oily     0.6390    0.6941    0.6654       510

    accuracy                         0.6534      1529
   macro avg     0.6544    0.6534    0.6532      1529
weighted avg     0.6544    0.6534    0.6532      1529
```