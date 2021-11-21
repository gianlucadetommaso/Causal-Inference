from models.normalizing_flow.made import ARMLP
from jax.random import PRNGKey
from jax import numpy as jnp
from flax.linen import Module
import jax

class MAF(Module):
    """ Masked Autoregressive Flow that uses a MADE-style network for fast forward """
    key: PRNGKey
    dim: int
    net_class: ARMLP = ARMLP
    parity: int = 0
    hidden_dim: int = 24

    def setup(self):
        self.net = self.net_class(self.key, self.dim*2, self.hidden_dim)
    def __call__(self,x):
        return self.forward(x)

    def forward(self, x):
        # here we see that we are evaluating all of z in parallel, so density estimation will be fast
        st = self.net(x)
        s, t = st.split(self.dim, axis=-1)
        z = x * jnp.exp(s) + t
        # reverse order, so if we stack MAFs correct things happen
        z = z.flip(dims=(1,)) if self.parity else z
        log_det = jnp.sum(s, axis=-1)
        return z, log_det
    
    def backward(self, z):
        # we have to decode the x one at a time, sequentially
        x = jnp.zeros_like(z)
        log_det = jnp.zeros(z.shape(0))
        z = z.flip(dims=(1,)) if self.parity else z
        for i in range(self.dim):
            st = self.net(x.copy()) # clone to avoid in-place op errors if using IAF
            s, t = st.split(self.dim, dim=1)
            x.at[:, i] = (z[:, i] - t[:, i]) * jnp.exp(-s[:, i])
            log_det += -s[:, i]
        return x, log_det

class IAF(MAF):
    def forward(self, z):
        return super().backward(z)
    def backward(self, x):
        return super().forward(x)


if __name__ == '__main__':
    key = jax.random.PRNGKey(0)
    
    #net = MyDense(64)
    net = ARMLP(key, 2, 24) 
    x = jnp.ones((32,2))
    params = net.init(key, x)
    key = jax.random.split(key)[0]
    flow = MAF(key, 2)
    params_flow = flow.init(key, x)

    print(flow.apply(params_flow, x)[1].shape)