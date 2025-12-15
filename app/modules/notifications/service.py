import logging

from flask import current_app
from flask_mail import Mail, Message

from app.modules.auth.models import User
from app.modules.dataset.models import DataSet

mail = Mail()
logger = logging.getLogger(__name__)


def init_mail(app):
    """Inicializa Flask-Mail con la app principal."""
    mail.init_app(app)
    logger.info("Flask-Mail initialized successfully")


def send_email(subject, recipients, body):
    """Envía un correo utilizando Flask-Mail."""
    logger.info("\n" + "=" * 80)
    logger.info("EMAIL SENDING INITIATED")
    logger.info(f"Subject: {subject}")
    logger.info(f"Recipients: {recipients}")
    logger.info(f"Body length: {len(body)} characters")

    try:
        msg = Message(subject, recipients=recipients, body=body)
        with current_app.app_context():
            mail.send(msg)
        logger.info(f"✓ EMAIL SENT SUCCESSFULLY to {recipients}")
        logger.info(f"{'='*80}\n")
        print(f"[SUCCESS] Email sent to {recipients} with subject: {subject}")
    except Exception as e:
        logger.error(f"✗ EMAIL SENDING FAILED for {recipients}")
        logger.error(f"Error: {str(e)}")
        logger.error(f"{'='*80}\n")
        print(f"[ERROR] Failed to send email to {recipients}: {str(e)}")
        raise


def send_dataset_accepted_email(proposal):
    """
    Envía un correo cuando un dataset es aceptado en una comunidad.
    """
    dataset = DataSet.query.get(proposal.dataset_id)
    if not dataset:
        logger.warning(f"Dataset not found for proposal ID: {proposal.dataset_id}")
        return

    owner = User.query.get(dataset.user_id)
    proposer = User.query.get(proposal.proposed_by)

    recipients = set()

    if owner and owner.email:
        recipients.add(owner.email)
        logger.debug(f"Added owner email: {owner.email}")

    if proposer and proposer.email:
        recipients.add(proposer.email)
        logger.debug(f"Added proposer email: {proposer.email}")

    if not recipients:
        logger.warning(f"No recipients found for proposal dataset ID: {proposal.dataset_id}")
        return

    community = proposal.community
    community_name = community.name
    dataset_title = dataset.ds_meta_data.title

    subject = f"Dataset aceptado en {community_name}"

    body = (
        f"Hola,\n\n"
        f'Tu dataset con ID {dataset.id} y título "{dataset_title}" '
        f'ha sido aceptado en la comunidad "{community_name}".\n\n'
        f"¡Enhorabuena!\n\n"
        f"— WeatherHub Team"
    )

    logger.info(f"Preparing to send acceptance email for dataset '{dataset_title}' " f"in community '{community_name}'")
    send_email(subject, list(recipients), body)
