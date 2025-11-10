import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataSet, DSMetaData, DSMetrics, PublicationType
from app.modules.dataset.validator import REQUIRED_COLUMNS
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder


class DataSetSeeder(BaseSeeder):
    priority = 2  # Lower priority

    def run(self):
        # Retrieve users
        user1 = User.query.filter_by(email="user1@example.com").first()
        user2 = User.query.filter_by(email="user2@example.com").first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        # Create DSMetrics instance
        ds_metrics = DSMetrics(number_of_models="5", number_of_features="50")
        seeded_ds_metrics = self.seed([ds_metrics])[0]

        # Create DSMetaData instances
        ds_meta_data_list = [
            DSMetaData(
                deposition_id=1 + i,
                title=f"Sample dataset {i+1}",
                description=f"Description for dataset {i+1}",
                publication_type=PublicationType.NONE.name,
                publication_doi=f"10.1234/dataset{i+1}",
                dataset_doi=f"10.1234/dataset{i+1}",
                tags="tag1, tag2",
                ds_metrics_id=seeded_ds_metrics.id,
            )
            for i in range(4)
        ]
        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # Create Author instances and associate with DSMetaData
        authors = [
            Author(
                name=f"Author {i+1}",
                affiliation=f"Affiliation {i+1}",
                orcid=f"0000-0000-0000-000{i}",
                ds_meta_data_id=seeded_ds_meta_data[i % 4].id,
            )
            for i in range(4)
        ]
        self.seed(authors)

        # Create DataSet instances
        datasets = [
            DataSet(
                user_id=user1.id if i % 2 == 0 else user2.id,
                ds_meta_data_id=seeded_ds_meta_data[i].id,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(4)
        ]
        seeded_datasets = self.seed(datasets)

        # For each dataset create one CSV and one README (md)
        fm_meta_data_list = []
        for i in range(len(seeded_datasets)):
            fm_meta_data_list.append(
                FMMetaData(
                    filename=f"dataset_{i+1}.csv",
                    title=f"Dataset file {i+1}",
                    description=f"CSV data file for dataset {i+1}",
                    publication_type=PublicationType.NONE.name,
                    publication_doi=f"10.1234/fm{i+1}",
                    tags="tag1, tag2",
                    version="1.0",
                )
            )

        seeded_fm_meta_data = self.seed(fm_meta_data_list)

        # Create one FeatureModel per dataset and attach FMMetaData
        feature_models = [
            FeatureModel(data_set_id=seeded_datasets[i].id, fm_meta_data_id=seeded_fm_meta_data[i].id)
            for i in range(len(seeded_datasets))
        ]
        seeded_feature_models = self.seed(feature_models)

        # Create CSV and README files programmatically and associate them with FeatureModels
        load_dotenv()
        working_dir = os.getenv("WORKING_DIR", "")
        for i, feature_model in enumerate(seeded_feature_models):
            dataset = next(ds for ds in seeded_datasets if ds.id == feature_model.data_set_id)
            user_id = dataset.user_id
            dest_folder = os.path.join(working_dir, "uploads", f"user_{user_id}", f"dataset_{dataset.id}")
            os.makedirs(dest_folder, exist_ok=True)

            # CSV file
            csv_name = feature_model.fm_meta_data.filename
            csv_path = os.path.join(dest_folder, csv_name)
            # write a minimal CSV with required headers
            with open(csv_path, "w", encoding="utf-8") as fh:
                fh.write(",".join([c.lstrip("_") for c in REQUIRED_COLUMNS]) + "\n")
                fh.write(",".join(["0" for _ in REQUIRED_COLUMNS]) + "\n")

            # README file
            readme_name = f"README_{i+1}.md"
            readme_path = os.path.join(dest_folder, readme_name)
            with open(readme_path, "w", encoding="utf-8") as fh:
                fh.write(f"# README for dataset {dataset.id}\n\nThis is a seeded README file.\n")

            # Create Hubfile entries for CSV and README
            csv_file = Hubfile(
                name=csv_name,
                checksum=f"checksum_csv_{i+1}",
                size=os.path.getsize(csv_path),
                feature_model_id=feature_model.id,
            )
            readme_file = Hubfile(
                name=readme_name,
                checksum=f"checksum_readme_{i+1}",
                size=os.path.getsize(readme_path),
                feature_model_id=feature_model.id,
            )
            self.seed([csv_file, readme_file])
