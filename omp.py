"""
omp.py

Author: James Ashton Nichols
Start date: April 2017

Some code to test various orthogonal-matching pursuit (OMP) algorithms in 1 dimension. 
Possibly will extend to 2 dimensions at some point.
"""

import math
import numpy as np
import scipy as sp
import collections

from itertools import *
import inspect
import copy

import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib import cm 
from mpl_toolkits.mplot3d import axes3d, Axes3D

import pdb

def sin_evaluate(x, freq):
    # nb we allow both freq and x to be np arrays
    # returns an array of size len(x) * len(freq)
    return np.sin(math.pi * freq * x) * math.sqrt(2.0) / (math.pi * freq)
        
def del_evaluate(x, x0):
    # nb we allow both x0 and x to be np arrays
    # returns an array of size len(x) * len(x0)
    normaliser =  1. / np.sqrt((1. - x0) * x0)
    
    choice = x <= x0 #np.array([x > x0ref for x0ref in x0])

    lower = x * (1. - x0) * normaliser
    upper = x0 * (1. - x) * normaliser
    
    if np.isscalar(choice):
        return lower * choice + upper * (not choice)

    return lower * choice + upper * (~choice)

def dot_type(s_p, s_c, s_ft, o_p, o_c, o_ft):
    d = 0.0
    for rp, rc in zip(s_p, s_c):
        for lp, lc in zip(o_p, o_c):
            d += dot_element(s_ft, rp, rc, o_ft, lp, lc)
    return d

def dot_element(lt, lp, lc, rt, rp, rc):
    dot = 0.0
    if lt == 'H1delta':
        c = 1.0 / np.sqrt(lp * (1.0 - lp))
        if rt == 'H1sin':
            dot += c * lc * rc * sin_evaluate(x = lp, freq = rp)
        elif rt == 'H1delta':
            dot += c * lc * rc * del_evaluate(x = lp, x0 = rp)
    elif lt == 'H1sin':
        if rt == 'H1sin':
            dot += lc * rc * (lp == rp).sum()
        elif rt == 'H1delta':
            c = 1.0 / np.sqrt(rp * (1.0 - rp))
            dot += c * lc * rc * sin_evaluate(x = rp, freq = lp)
    return dot

def dot_element_array(lt, lp, lc, rt, rp, rc):
    dot = 0.0
    if lt == 'H1delta':
        for p in lp:
            c = 1.0 / np.sqrt(p * (1.0 - p))
            if rt == 'H1sin':
                dot += (c * sin_evaluate(x = p, freq = rp)).sum()
            elif rt == 'H1delta':
                dot += (c * del_evaluate(x = p, x0 = rp)).sum()
    elif lt == 'H1sin':
        for p in lp:
            if rt == 'H1sin':
                dot += (p == rp).sum()
            elif rt == 'H1delta':
                c = 1.0 / np.sqrt(rp * (1.0 - rp))
                dot += (c * sin_evaluate(x = rp, freq = p)).sum()
    return dot

# Define a basis as a collection of elements

# Write the dictionary and Basis class, and basis pair class, in terms of these elements
# Make that Basis class the same as the Basis class in the dyadic FEM code one day, so that this
# Can all become part of the same library

# Define the OMP algorithm from there on...


class Vector(object):
    
    # Ok new paradigm - use numpy to be a bit faster...

    def __init__(self, params=None, coeffs=None, fn_types=None):
        
        self.params = []
        self.coeffs = []
        self.fn_types = []

        if params is not None and fn_types is not None and coeffs is not None:

            if len(params) != len(fn_types) or len(coeffs) != len(fn_types):
                raise Exception('Need as many parameters and coefficients as func types')

            self.fn_types = fn_types
            self.n_types = len(self.fn_types)
            
            for i in range(self.n_types):
                if np.isscalar(params[i]):
                    # Don't sort if singleton
                    self.params.append(np.array([params[i]]))
                    self.coeffs.append(np.array([coeffs[i]]))
                else:
                    s = np.argsort(params[i])
                    self.params.append(np.array(params[i])[s])
                    self.coeffs.append(np.array(coeffs[i])[s])

    def dot(self, other):
        # To keep values *exact* we do the dot product between all the elements of the dictionary

        d = 0.0
        
        for s_p, s_c, s_ft in zip(self.params, self.coeffs, self.fn_types):
            for o_p, o_c, o_ft in zip(other.params, other.coeffs, other.fn_types):
                d += dot_type(s_p, s_c, s_ft, o_p, o_c, o_ft)

        #for s_n, s_ft in enumerate(self.fn_types):
        #    for o_n, o_ft in enumerate(other.fn_types):
        #        d += ([s_c * o_c * dot_element(s_ft, s_p, o_ft, o_p) \
        #               for s_p, s_c in zip(self.params[s_n], self.coeffs[s_n]) \
        #               for o_p, o_c in zip(other.params[o_n], other.coeffs[o_n])]).sum()

                #d += dot_element(s_ft, self.params[s_n], o_ft, other.params[o_n])

        return d
   
    def norm(self):
        return math.sqrt(self.dot(self))

    def evaluate(self, x):
        val = np.zeros(x.shape)
        for fn_i, fn_type in enumerate(self.fn_types):
            if fn_type == 'H1sin':
                for p, c in zip(self.params[fn_i], self.coeffs[fn_i]):
                    val += c * sin_evaluate(x, p)
                #for p_i in range(len(self.params[fn_i])):
                #    val += self.coeffs[fn_i][p_i] * sin_evaluate(x, self.params[fn_i][p_i])
            if fn_type == 'H1delta':
                for p, c in zip(self.params[fn_i], self.coeffs[fn_i]):
                    val += c * del_evaluate(x, p)
                #for p_i in range(len(self.params[fn_i])):
                #    val += self.coeffs[fn_i][p_i] * del_evaluate(x, self.params[fn_i][p_i])
        return val


    def merge_type(self, p, c, fn_type):

        if fn_type not in self.fn_types:
            self.fn_types.append(fn_type)
            self.params.append(np.array([]))
            self.coeffs.append(np.array([]))
        
        i = self.fn_types.index(fn_type)

        # The strange task of merging our sorted numpy arrays...
        self.params[i] = np.append(self.params[i], p)
        self.coeffs[i] = np.append(self.coeffs[i], c)

        s = np.argsort(self.params[i])

        self.params[i] = self.params[i][s]
        self.coeffs[i] = self.coeffs[i][s]
        
        self.params[i], inv = np.unique(self.params[i], return_inverse=True)
        self.coeffs[i] = np.bincount(inv, self.coeffs[i])
       
    def __add__(self, other):
        result = copy.deepcopy(self)
        for o_fn_i, fn_type in enumerate(other.fn_types):
            result.merge_type(other.params[o_fn_i], other.coeffs[o_fn_i], fn_type)

        return result

    __radd__ = __add__

    def __iadd__(self, other):
        for o_fn_i, fn_type in enumerate(other.fn_types):
            self.merge_type(other.params[o_fn_i], other.coeffs[o_fn_i], fn_type)

        return self 
     
    def __sub__(self, other):
        result = copy.deepcopy(self)
        for o_fn_i, fn_type in enumerate(other.fn_types):
            result.merge_type(other.params[o_fn_i], -other.coeffs[o_fn_i], fn_type)

        return result

    __rsub__ = __sub__

    def __isub__(self, other):
        for o_fn_i, fn_type in enumerate(other.fn_types):
            self.merge_type(other.params[o_fn_i], -other.coeffs[o_fn_i], fn_type)

        return self 

    def __neg__(self):
        result = copy.deepcopy(self)
        for c in result.coeffs:
            c = -c
        return result
 
    def __pos__(self):
        result = copy.deepcopy(self)
        for c in result.coeffs:
            c = +c

    def __mul__(self, other):
        result = copy.deepcopy(self)
        for c in result.coeffs:
            c *= other
        return result

    __rmul__ = __mul__

    def __truediv__(self, other):
        result = copy.deepcopy(self)
        for c in self.coeffs:
            c /= other
        return result

class Basis(object):
    """ A vaguely useful encapsulation of what you'd wanna do with a basis,
        including an orthonormalisation procedure """

    def __init__(self, vecs=None):
        
        if vecs is not None:
            self.vecs = vecs
            self.n = len(vecs)

            self.orthonormal_basis = None
            self.G = None
            self.U = self.S = self.V = None

    def add_vector(self, vec):
        """ Add just one vector, so as to make the new Grammian calculation quick """

        self.vecs.append(vec)
        self.n += 1

        if self.G is not None:
            self.G = np.pad(self.G, ((0,1),(0,1)), 'constant')
            for i in range(self.n):
                self.G[self.n-1, i] = self.G[i, self.n-1] = self.vecs[-1].dot(self.vecs[i])

        self.U = self.V = self.S = None

    def subspace(self, indices):
        """ To be able to do "nested" spaces, the easiest way is to implement
            subspaces such that we can draw from a larger ambient space """
        sub = type(self)(self.vecs[indices])

        if self.G is not None:
            sub.G = self.G[indices, indices]
        return G

    def subspace_mask(self, mask):
        """ Here we make a subspace by using a boolean mask that needs to be of
            the same size as the number of vectors. Used for the cross validation """
        if mask.shape[0] != len(self.vecs):
            raise Exception('Subspace mask must be the same size as length of vectors')

        sub = type(self)(list(compress(self.vecs, mask)))
        if self.G is not None:
            sub.G = self.G[mask,mask]
        return sub

    def dot(self, u):
        u_d = np.zeros(self.n)
        for i, v in enumerate(self.vecs):
            u_d[i] = v.dot(u)
        return u_d

    def make_grammian(self):
        if self.G is None:
            self.G = np.zeros([self.n,self.n])
            for i in range(self.n):
                for j in range(i+1):
                    self.G[i,j] = self.G[j,i] = self.vecs[i].dot(self.vecs[j])

    def cross_grammian(self, other):
        CG = np.zeros([self.n, other.n])
        
        for i in range(self.n):
            for j in range(other.n):
                CG[i,j] = self.vecs[i].dot(other.vecs[j])
        return CG

    def project(self, u):
        
        # Either we've made the orthonormal basis...
        if self.orthonormal_basis is not None:
            return self.orthonormal_basis.project(u) 
        else:
            if self.G is None:
                self.make_grammian()

            u_n = self.dot(u)
            try:
                if sp.sparse.issparse(self.G):
                    y_n = sp.sparse.linalg.spsolve(self.G, u_n)
                else:
                    y_n = sp.linalg.solve(self.G, u_n, sym_pos=True)
            except np.linalg.LinAlgError as e:
                print('Warning - basis is linearly dependent with {0} vectors, projecting using SVD'.format(self.n))

                if self.U is None:
                    if sp.sparse.issparse(self.G):
                        self.U, self.S, self.V =  sp.sparse.linalg.svds(self.G)
                    else:
                        self.U, self.S, self.V = np.linalg.svd(self.G)
                # This is the projection on the reduced rank basis 
                y_n = self.V.T @ ((self.U.T @ u_n) / self.S)

            # We allow the projection to be of the same type 
            # Also create it from the simple broadcast and sum (which surely should
            # be equivalent to some tensor product thing??)
            #u_p = type(self.vecs[0])((y_n * self.values_flat).sum(axis=2)) 
        
            return self.reconstruct(y_n)

    def reconstruct(self, c):
        # Build a function from a vector of coefficients
        if len(c) != len(self.vecs):
            raise Exception('Coefficients and vectors must be of same length!')
         
        u_p = Vector()
        for i, c_i in enumerate(c):
            u_p += c_i * self.vecs[i] 
        return u_p

    def matrix_multiply(self, M):
        # Build another basis from a matrix, essentially just calls 
        # reconstruct for each row in M
        if M.shape[0] != M.shape[1] or M.shape[0] != self.n:
            raise Exception('M must be a {0}x{1} square matrix'.format(self.n, self.n))

        vecs = []
        for i in range(M.shape[0]):
            vecs.append(self.reconstruct(M[i,:]))
        
        return Basis(vecs)

    def ortho_matrix_multiply(self, M):
        # Build another basis from an orthonormal matrix, 
        # which means that the basis that comes from it
        # is also orthonormal *if* it was orthonormal to begin with
        if M.shape[0] != M.shape[1] or M.shape[0] != self.n:
            raise Exception('M must be a {0}x{1} square matrix'.format(self.n, self.n))

        vecs = []
        for i in range(M.shape[0]):
            vecs.append(self.reconstruct(M[i,:]))
        
        # In case this is an orthonormal basis
        return type(self)(vecs)

    def orthonormalise(self):

        if self.G is None:
            self.make_grammian()
        
        # We do a cholesky factorisation rather than a Gram Schmidt, as
        # we have a symmetric +ve definite matrix, so this is a cheap and
        # easy way to get an orthonormal basis from our previous basis
        
        if sp.sparse.issparse(self.G):
            L = sp.sparse.cholmod.cholesky(self.G)
        else:
            L = np.linalg.cholesky(self.G)
        L_inv = sp.linalg.lapack.dtrtri(L.T)[0]
        
        ortho_vecs = []
        for i in range(self.n):
            ortho_vecs.append(self.reconstruct(L_inv[:,i]))
                    
        self.orthonormal_basis = OrthonormalBasis(ortho_vecs)

        return self.orthonormal_basis

class OrthonormalBasis(Basis):

    def __init__(self, vecs=None):
        # We quite naively assume that the basis we are given *is* in 
        # fact orthonormal, and don't do any testing...

        super().__init__(vecs=vecs)
        #self.G = np.eye(self.n)
        #self.G = sp.sparse.identity(self.n)

    def project(self, u):
        # Now that the system is orthonormal, we don't need to solve a linear system
        # to make the projection
        return self.reconstruct(self.dot(u))

    def orthonormalise(self):
        return self


class BasisPair(object):
    """ This class automatically sets up the cross grammian, calculates
        beta, and can do the optimal reconstruction and calculated a favourable basis """

    def __init__(self, Wm, Vn, G=None):

        if Vn.n > Wm.n:
            raise Exception('Error - Wm must be of higher dimensionality than Vn')

        self.Wm = Wm
        self.Vn = Vn
        self.m = Wm.n
        self.n = Vn.n
        
        if G is not None:
            self.G = G
        else:
            self.G = self.cross_grammian()

        self.U = self.S = self.V = None

    def cross_grammian(self):
        CG = np.zeros([self.m, self.n])
        
        for i in range(self.m):
            for j in range(self.n):
                CG[i,j] = self.Wm.vecs[i].dot(self.Vn.vecs[j])
        return CG
    
    def beta(self):
        if self.U is None or self.S is None or self.V is None:
            self.calc_svd()

        return self.S[-1]

    def calc_svd(self):
        if self.U is None or self.S is None or self.V is None:
            self.U, self.S, self.V = np.linalg.svd(self.G)

    def make_favorable_basis(self):
        if isinstance(self, FavorableBasisPair):
            return self
        
        if not isinstance(self.Wm, OrthonormalBasis) or not isinstance(self.Vn, OrthonormalBasis):
            raise Exception('Both Wm and Vn must be orthonormal to calculate the favourable basis!')

        if self.U is None or self.S is None or self.V is None:
            self.calc_svd()

        fb = FavorableBasisPair(self.Wm.ortho_matrix_multiply(self.U.T), 
                                self.Vn.ortho_matrix_multiply(self.V),
                                S=self.S, U=np.eye(self.n), V=np.eye(self.m))
        return fb

    def measure_and_reconstruct(self, u, disp_cond=False):
        """ Just a little helper function. Not sure we really want this here """ 
        u_p_W = self.Wm.dot(u)
        return self.optimal_reconstruction(u_p_W, disp_cond)

    def optimal_reconstruction(self, w, disp_cond=False):
        """ And here it is - the optimal reconstruction """
        try:
            c = scipy.linalg.solve(self.G.T @ self.G, self.G.T @ w, sym_pos=True)
        except np.linalg.LinAlgError as e:
            print('Warning - unstable v* calculation, m={0}, n={1} for Wm and Vn, returning 0 function'.format(self.Wm.n, self.Vn.n))
            c = np.zeros(self.Vn.n)

        v_star = self.Vn.reconstruct(c)

        u_star = v_star + self.Wm.reconstruct(w - self.Wm.dot(v_star))

        # Note that W.project(v_star) = W.reconsrtuct(W.dot(v_star))
        # iff W is orthonormal...
        cond = np.linalg.cond(self.G.T @ self.G)
        if disp_cond:
            print('Condition number of G.T * G = {0}'.format(cond))
        
        return u_star, v_star, self.Wm.reconstruct(w), self.Wm.reconstruct(self.Wm.dot(v_star)), cond

class FavorableBasisPair(BasisPair):
    """ This class automatically sets up the cross grammian, calculates
        beta, and can do the optimal reconstruction and calculated a favourable basis """

    def __init__(self, Wm, Vn, S=None, U=None, V=None):
        # We quite naively assume that the basis we are given *is* in 
        # fact orthonormal, and don't do any testing...

        if S is not None:
            # Initialise with the Grammian equal to the singular values
            super().__init__(Wm, Vn, G=S)
            self.S = S
        else:
            super().__init__(Wm, Vn)
        if U is not None:
            self.U = U
        if V is not None:
            self.V = V

    def make_favorable_basis(self):
        return self

    def optimal_reconstruction(self, w, disp_cond=False):
        """ Optimal reconstruction is much easier with the favorable basis calculated 
            NB we have to assume that w is measured in terms of our basis Wn here... """
        
        w_tail = np.zeros(w.shape)
        w_tail[self.n:] = w[self.n:]
        
        v_star = self.Vn.reconstruct(w[:self.n] / self.S)
        u_star = v_star + self.Wm.reconstruct(w_tail)

        return u_star, v_star, self.Wm.reconstruct(w), self.Wm.reconstruct(self.Wm.dot(v_star))


"""
*****************************************************************************************
All the functions below are for building specific basis systems 
*****************************************************************************************
"""

def make_sin_basis(n):
    V_n = []

    # We want an ordering such that we get (1,1), (1,2), (2,1), (2,2), (2,3), (3,2), (3,1), (1,3), ...
    for i in range(1,n+1):
        v_i = Vector([i], [1.0], ['H1sin'])
        V_n.append(v_i)
            
    return OrthonormalBasis(V_n)


def make_random_delta_basis(n, bounds=None, bound_prop=1.0):

    vecs = []
    
    if bounds is not None:
        bound_points = (bounds[1] - bounds[0]) *  np.random.random(round(n * bound_prop)) + bounds[0]
        
        remain_points = (1.0 - (bounds[1] - bounds[0])) * np.random.random(round(n * (1.0 - bound_prop)))
        # Ooof remain points problem - first left
        if bounds[0] > 0.0:
            remain_l = remain_points[remain_points < bounds[0]]
            remain_r = remain_points[remain_points >= bounds[0]] + bounds[1]
            remain_points = np.append(remain_l, remain_r)
        else:
            remain_points += bounds[1]

        points = np.append(bound_points, remain_points)
    else:
        points = np.random.random(n)
        
    for i in range(n):
        v_i = Vector([points[i]], [1.0], ['H1delta']) 
        vecs.append(v_i)
    
    return Basis(vecs)

"""
*****************************************************************************************
All the functions below are for building bases from greedy algorithms. Several
variants are proposed here.
*****************************************************************************************
"""

def make_unif_dictionary(N):

    points, step = np.linspace(0.0, 1.0, N+1, endpoint=False, retstep=True)
    #points = points + 0.5 * step # Make midpoints... don't want 0.0 or 1.0
    points = points[1:] # Get rid of that first one!

    dic = [Vector([p],[1.0],['H1delta']) for p in points]

    return dic

def make_rand_dictionary(N):

    points = np.random.random(N)

    dic = [Vector([p],[1.0],['H1delta']) for p in points]

    return dic

class GreedyBasisConstructor(object):
    """ This is the original greedy algorithm that minimises the Kolmogorov n-width, and a 
        generic base-class for all other greedy algorithms """

    def __init__(self, m, dictionary, Vn, verbose=False, remove=True):
        """ We need to be either given a dictionary or a point generator that produces d-dimensional points
            from which we generate the dictionary. """
            
        self.dictionary = copy.copy(dictionary)

        self.m = m
        self.Vn = Vn

        self.verbose = verbose
        self.remove = remove
        self.greedy_basis = None

    def initial_choice(self):
        """ Different greedy methods will have their own maximising/minimising criteria, so all 
        inheritors of this class are expected to overwrite this method to suit their needs. """
    
        self.norms = np.zeros(len(self.dictionary))
        for i in range(len(self.dictionary)):
            for phi in self.Vn.vecs:
                self.norms[i] += phi.dot(self.dictionary[i]) ** 2

        n0 = np.argmax(self.norms)
        if self.remove:
            self.norms = np.delete(self.norms, n0)

        return n0

    def next_step_choice(self, i):
        """ Different greedy methods will have their own maximising/minimising criteria, so all 
        inheritors of this class are expected to overwrite this method to suit their needs. """

        next_crit = np.zeros(len(self.dictionary))
        # We go through the dictionary and find the max of || f ||^2 - || P_Vn f ||^2
        for phi in self.Vn.vecs:
            phi_perp = phi - self.greedy_basis.project(phi)
            for i in range(len(self.dictionary)):
                next_crit[i] = phi_perp.dot(self.dictionary[i]) ** 2
                #p_V_d[i] = self.greedy_basis.project(self.dictionary[i]).norm()
        
        ni = np.argmax(next_crit)

        if self.remove:
            self.norms = np.delete(self.norms, ni)

        if self.verbose:
            print('{0} : \t {1}'.format(i, next_crit[ni]))

        return ni

    def construct_basis(self):
        " The construction method should be generic enough to support all variants of the greedy algorithms """
        
        if self.greedy_basis is None:
            n0 = self.initial_choice()

            self.greedy_basis = Basis([self.dictionary[n0]])
            self.greedy_basis.make_grammian()
            
            if self.remove:
                del self.dictionary[n0]

            if self.verbose:
                print('\n\nGenerating basis from greedy algorithm with dictionary: ')
                print('i \t || phi_i || \t\t || phi_i - P_V_(i-1) phi_i ||')

            for i in range(1, self.m):
                
                ni = self.next_step_choice(i)
                    
                self.greedy_basis.add_vector(self.dictionary[ni])
                if self.remove:
                    del self.dictionary[ni]
                       
            if self.verbose:
                print('\n\nDone!')
        else:
            print('Greedy basis already computed!')

        return self.greedy_basis

