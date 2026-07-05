def saxton_rawls_fraction(S, C, OM):
    # S, C are fractions (0-1), OM is %
    theta_1500t = -0.024*S + 0.487*C + 0.006*OM + 0.005*(S*OM) - 0.013*(C*OM) + 0.068*(S*C) + 0.031
    theta_1500 = theta_1500t + (0.14 * theta_1500t - 0.02)
    
    theta_33t = -0.251*S + 0.195*C + 0.011*OM + 0.006*(S*OM) - 0.027*(C*OM) + 0.452*(S*C) + 0.299
    theta_33 = theta_33t + (1.283 * (theta_33t**2) - 0.374 * theta_33t - 0.015)
    
    return theta_33, theta_1500

def saxton_rawls_percent(S, C, OM):
    # S, C are percentages (0-100), OM is %
    theta_1500t = -0.024*S + 0.487*C + 0.006*OM + 0.005*(S*OM) - 0.013*(C*OM) + 0.068*(S*C) + 0.031
    theta_1500 = theta_1500t + (0.14 * theta_1500t - 0.02)
    
    theta_33t = -0.251*S + 0.195*C + 0.011*OM + 0.006*(S*OM) - 0.027*(C*OM) + 0.452*(S*C) + 0.299
    theta_33 = theta_33t + (1.283 * (theta_33t**2) - 0.374 * theta_33t - 0.015)
    
    return theta_33, theta_1500

print("Fractions (Loam: S=0.4, C=0.2, OM=2.0%):", saxton_rawls_fraction(0.4, 0.2, 2.0))
print("Percentages (Loam: S=40, C=20, OM=2.0%):", saxton_rawls_percent(40, 20, 2.0))
