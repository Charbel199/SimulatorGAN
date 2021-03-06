import torchvision
import torch
from torch.utils.tensorboard import SummaryWriter
from model.discriminator import Discriminator
from model.generator import Generator
from model.weights import initialize_model_weights
import torch.optim as optim
import torch.nn as nn
from dataset import get_loaders
from model.preprocessing import get_transforms
from conf import ModelConfig
from torchsummary import summary
import torch.nn.functional as F


def train_fn(generator,
             discriminator,
             loader,
             noise_dimension,
             criterion,
             opt_discriminator,
             opt_generator,
             epochs,
             writer_fake,
             writer_real,
             fixed_noise,
             device='cpu'):
    step = 0
    generator.train()
    discriminator.train()

    for epoch in range(epochs):
        for batch_idx, real_image in enumerate(loader):
            batch_size = real_image.shape[0]

            ## Fetching real image and generating FAKE image
            # Real image represents the actual MNIST image
            real_image = real_image.to(device)
            real_image = F.one_hot(real_image.long())
            real_image = torch.moveaxis(real_image, -1, 1)
            # Noise represents a random matrix of noise used by the generator as input
            noise = torch.randn(batch_size, noise_dimension, 1, 1).to(device)
            fake_image = generator(noise)
            ## Train discriminator, maximize (log(D(real)) + log(1-D(G(z))))
            # log(D(real)) part
            discriminator_real = discriminator(real_image.float())
            loss_discriminator_real = criterion(discriminator_real, torch.ones_like(
                discriminator_real))  # Discriminator should associate real image with  1
            # log(1-D(G(z)) part
            discriminator_fake = discriminator(fake_image).view(-1)
            loss_discriminator_fake = criterion(discriminator_fake, torch.zeros_like(
                discriminator_fake))  # Discriminator should associate fake image with  0
            # Combined loss
            loss_discriminator = (loss_discriminator_real + loss_discriminator_fake) / 2

            discriminator.zero_grad()
            # loss.backward() sets the grad attribute of all tensors with requires_grad=True in the computational graph
            loss_discriminator.backward(
                retain_graph=True)  # retrain_graph so that what was used in this pass is not cleared from cache, ex: fake_image
            opt_discriminator.step()

            ## Train generator, minimize log(1-D(G(z))) OR maximize log(D(G(z)))
            # log(D(G(z)) part
            discriminator_fake = discriminator(fake_image).view(-1)
            loss_generator = criterion(discriminator_fake, torch.ones_like(
                discriminator_fake))  # Generator wants Discriminator to associate fake image with  1

            generator.zero_grad()
            loss_generator.backward(
                retain_graph=True)  # retrain_graph so that what was used in this pass is not cleared from cache, ex: fake_image
            opt_generator.step()

            # Tensorboard code
            # if batch_idx == 0:
            #     print(
            #         f"Epoch [{epoch}/{epochs}] Batch {batch_idx}/{len(loader)} \
            #               Loss D: {loss_discriminator:.4f}, loss G: {loss_generator:.4f}"
            #     )
            #
            #     with torch.no_grad():
            #         fake = generator(fixed_noise)
            #         img_grid_fake = torchvision.utils.make_grid(fake[:32], normalize=True)
            #         img_grid_real = torchvision.utils.make_grid(real_image[:32], normalize=True)
            #
            #         writer_fake.add_image(
            #             "Fake Images", img_grid_fake, global_step=step
            #         )
            #         writer_real.add_image(
            #             "Real Images", img_grid_real, global_step=step
            #         )
            #         step += 1
            # else:
            #     print(f"Batch {batch_idx}/{len(loader)}")


def train_model(config: ModelConfig):
    fixed_noise = torch.randn(config.batch_size, config.noise_dimension, 1, 1).to(config.device)
    writer_fake = SummaryWriter(f"assets/logs/runs/fake")  # For fake images
    writer_real = SummaryWriter(f"assets/logs/runs/real")  # For real images

    discriminator = Discriminator(config.number_of_classes, config.features_discriminator, 2).to(config.device)
    initialize_model_weights(discriminator)
    generator = Generator(config.noise_dimension, config.number_of_classes, config.features_generator, config.kernel_size).to(config.device)
    initialize_model_weights(generator)

    summary(generator, (config.noise_dimension, 1, 1), device=config.device)
    summary(discriminator, (config.number_of_classes, config.size, config.size), device=config.device)

    opt_discriminator = optim.Adam(discriminator.parameters(), lr=config.learning_rate, betas=(0.5, 0.999))
    opt_generator = optim.Adam(generator.parameters(), lr=config.learning_rate, betas=(0.5, 0.999))
    criterion = nn.BCELoss()  # Loss function

    # Assuming same transform for train and val
    # transforms = get_transforms(
    #     size=config.size,
    #     number_of_channels=config.number_of_classes
    # )
    transforms = None

    training_loader, _ = get_loaders(
        train_dir=config.train_path,
        val_dir=config.val_path,
        batch_size=config.batch_size,
        train_transform=transforms,
        val_transform=transforms,
        num_workers=4,
        pin_memory=True,
    )

    train_fn(
        generator=generator,
        discriminator=discriminator,
        loader=training_loader,
        noise_dimension=config.noise_dimension,
        criterion=criterion,
        opt_discriminator=opt_discriminator,
        opt_generator=opt_generator,
        epochs=config.epoch,
        writer_fake=writer_fake,
        writer_real=writer_real,
        fixed_noise=fixed_noise,
        device=config.device
    )
