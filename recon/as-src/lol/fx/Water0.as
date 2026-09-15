class lol.fx.Water0 extends MovieClip
{
   var layer_mc0;
   var layer_mc1;
   var onEnterFrame;
   var count = 0;
   var maxCount = 50;
   function Water0(bm)
   {
      super();
      this.createLayers(bm);
      this.start();
   }
   function createLayers(bm)
   {
      this.layer_mc0 = this.createEmptyMovieClip("layer_mc0",0);
      this.layer_mc1 = this.createEmptyMovieClip("layer_mc1",1);
      this.layer_mc0.attachBitmap(bm,0);
      this.layer_mc1.attachBitmap(bm,0);
      this.layer_mc1._rotation = 180;
      this.layer_mc1._x = this.layer_mc1._width;
      this.layer_mc1._y = this.layer_mc1._height;
   }
   function start()
   {
      this.layer_mc0._x = 5;
      this.layer_mc1._alpha = 100;
      this.count = 0;
      this.onEnterFrame = this.playFX;
   }
   function playFX()
   {
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.WATER_ANIMATION))
      {
         this.move0();
         if(this.count <= 0.5 * this.maxCount)
         {
            this.fadeDown();
         }
         else
         {
            this.fadeUp();
         }
         this.count = this.count + 1;
         if(this.count >= this.maxCount)
         {
            this.start();
         }
      }
   }
   function move0()
   {
      var _loc2_ = 10 / this.maxCount;
      this.layer_mc0._x -= _loc2_;
   }
   function fadeUp()
   {
      this.layer_mc1._alpha += 200 / this.maxCount;
   }
   function fadeDown()
   {
      this.layer_mc1._alpha -= 200 / this.maxCount;
   }
}
