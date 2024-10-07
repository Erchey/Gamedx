from database import engine
import pandas as pd

csv_file_path = r'C:\Users\Kingsley\Documents\Gamedx\SchoolApp\csvs\First-term.csv'  # Adjust the path as necessary
df = pd.read_csv(csv_file_path)
df.head()

df_selected = df['SUBJECTS']

for index, row in df_selected.iterrows():
    # Query the subject by subject_id (or whichever column you're using as an identifier)
    subject_record = session.query(Subjects).filter(Subjects.id == row['subject_id']).first()

    if subject_record:
        # Update the subject name with the new value from df_selected
        subject_record.subject = row['subject']

# Commit the session to apply the changes to the database
session.commit()

# Close the session when done
session.close()
