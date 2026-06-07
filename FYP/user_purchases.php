<?php
session_start();


if (!isset($_SESSION['logged_in']) || $_SESSION['logged_in'] !== true) {
    header('Location: login.php');
    exit;
}


$purchased_products = [
    [
        'name' => 'Cat Cup',
        'image' => 'assets/images/products/product_square/mTx1.webp',
        'purchase_date' => '2026-05-10',
        'price' => '$15.00'
    ],
    [
        'name' => 'Hedgehog Cup',
        'image' => 'assets/images/products/product_square/mtx2.jpeg',
        'purchase_date' => '2026-05-15',
        'price' => '$18.00'
    ],
    [
        'name' => 'Fox Cup',
        'image' => 'assets/images/products/mtx4.jpg',
        'purchase_date' => '2026-06-01',
        'price' => '$20.00'
    ]
];
?>
<!DOCTYPE html>
<html lang="en" dir="ltr">

  <head>
    <meta charset="utf-8">
    <title>AssistFlow - My Purchases</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link rel="shortcut icon" href="assets/images/favicon.png" type="image/png">
    <link rel="icon" href="assets/images/favicon.png" type="image/png">
    <link rel="stylesheet" href="assets/icons/themify-icons/themify-icons.css">
    <link rel="stylesheet" href="assets/css/vendor/bootstrap.min.css">
    <link rel="stylesheet" href="assets/css/main.css">
  </head>

  <body>

    <header class="site_header">
      <div class="container-fluid px-0">
        <div class="row no-gutters">
          <div class="col-12">
            <div class="slim_topbar">
              <h6>Free domestic Canada office delivery over $500 order</h6>
            </div>
          </div>
        </div>
        <div class="row no-gutters">
          <div class="col-12">
            <nav class="navbar navbar-expand-lg fixed-top pb-0 navbar_top">
              <a class="navbar-brand" href="#" data-toggle="modal" data-target="#icon_modal_location">
                <img src="assets/images/gmap.png" alt="Google map icon">
              </a>
              <a href="index.php" class="ml-auto mr-auto"><img src="assets/images/assistflow-logo.png" alt="AssistFlow's logo" class="site_logo" style="height: 55px;"></a>
              <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navToggler" aria-controls="navToggler" aria-expanded="false" aria-label="Toggle navigation">
                <spna class="ti-menu"></spna>
              </button>
              <div class="collapse navbar-collapse" id="navToggler" style="flex-grow: 0;">
                <ul class="navbar-nav ml-auto">
                  <li class="nav-item">
                    <a class="nav-link" href="index.php">Home</a>
                  </li>
                  <li class="nav-item">
                    <a class="nav-link" href="products.php">Products</a>
                  </li>
                  <li class="nav-item">
                    <a class="nav-link" href="faq.php">FAQ</a>
                  </li>
                  <li class="nav-item">
                    <a class="nav-link" href="contact.php">Contact</a>
                  </li>
                  <li class="nav-item" style="display: flex; align-items: center;">
                    <a class="nav-link" href="login.php" style="padding: 0.5rem 1rem;">
                      <img src="assets/images/login.png" alt="Login" style="height: 20px;">
                    </a>
                  </li>
                </ul>
              </div>
            </nav>
          </div>
        </div>
      </div>
    </header>

    <section class="site_banner_inner">
      <div class="container-fluid px-0">
        <div class="row no-gutters">
          <div class="col-12">
            <div class="banner_overlay_inner">
              <div class="banner_heading_inner">
                <h2 class="text-white text-center mb-0 mt-3">My Account</h2>
                <h3 class="text-white text-center">Your Past Purchases</h3>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="products pt-5 pb-5">
      <div class="container">
        <div class="row mb-3 mt-5">
          <div class="col-12 text-center">
            <h2 class="section-title">Purchase History</h2>
            <p class="section-subtitle mb-5">Welcome back, testing!</p>
          </div>
        </div>
        <div class="row">
          <?php foreach ($purchased_products as $product): ?>
            <div class="col-md-4 mb-4">
              <div class="card h-100 shadow-sm">
                <img src="<?php echo htmlspecialchars($product['image']); ?>" class="card-img-top" alt="<?php echo htmlspecialchars($product['name']); ?>" style="object-fit: cover; height: 300px;">
                <div class="card-body">
                  <h5 class="card-title"><?php echo htmlspecialchars($product['name']); ?></h5>
                  <p class="card-text"><strong>Price:</strong> <?php echo htmlspecialchars($product['price']); ?></p>
                  <p class="card-text"><small class="text-muted">Purchased on <?php echo htmlspecialchars($product['purchase_date']); ?></small></p>
                </div>
              </div>
            </div>
          <?php endforeach; ?>
        </div>
        <div class="row mt-4">
           <div class="col-12 text-center">
             <a href="logout.php" class="btn btn-danger">Logout</a>
           </div>
        </div>
      </div>
    </section>

    <footer class="site_footer pt-5 pb-5">
      <div class="container">
        <div class="row">
          <div class="col-md-4">
            <ul class="list_group footer_list">
              <li class="list_group_item">
                <a href="index.php" class="footer_logo">
                  <img class="" src="assets/images/assistflow-logo.png" alt="AssistFlow logo">
                </a>
              </li>
              <li class="list_group_item">
                <p class="py-3">AssistFlow provides a delightful Animal Cup collection designed to bring joy to your mornings. Our success is due to a deep understanding of adorable animals and a drive to deliver cute experiences.</p>
              </li>
              <li class="list_group_item">
                <p class="pb-0 mb-0 h6">
                  <i class="ti-headphone mr-1"></i>
                  (123) 123 123
                </p>
              </li>
              <li class="list_group_item h6">
                <p class="">
                  <i class="ti-email mr-1"></i>
                  AssistFlow@gmail.com
                </p>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </footer>

    <div class="copyright">
      <div class="container">
        <div class="row">
          <div class="col-md-6">
            <p>Copyright@AssistFlow 2026</p>
          </div>
        </div>
      </div>
    </div>

    <script src="assets/js/vendor/jquery.min.js" charset="utf-8"></script>
    <script src="assets/js/vendor/bootstrap.bundle.min.js" charset="utf-8"></script>
    <script src="assets/js/main.js" charset="utf-8"></script>
  </body>
</html>

